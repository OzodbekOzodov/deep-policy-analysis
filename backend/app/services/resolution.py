"""Entity Resolution Service - Smart Deduplication with Relationship Preservation

Implements multi-tier deduplication:
- Tier 1: Alias dictionary + exact/fuzzy matching (fast)
- Tier 3: LLM batch confirmation (accurate)

Relationships are preserved during entity merges through remapping.
"""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Optional, Any, Set
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.dialects.postgresql import insert

from app.models.database import Entity, EntityProvenance, Relationship, EntityMergeLog
from app.clients.llm import LLMClient, get_llm_client
from app.entity_aliases_data import get_canonical_label, is_alias_match

logger = logging.getLogger(__name__)


# LLM Prompts
BATCH_MERGE_PROMPT = """Review these groups of potentially duplicate entities.

For each group, determine if they should be merged and select the canonical label.

Entity Groups:
{groups}

Consider:
- Abbreviations/acronyms (e.g., "Ministry of Defense" and "MoD")
- Variations in naming (e.g., "US Congress" and "United States Congress")
- Spelling variations and minor typos
- Whether they refer to the same real-world entity

Return JSON:
{{
    "decisions": [
        {{
            "group_id": <group number>,
            "should_merge": true/false,
            "canonical_label": "<preferred name if merging>",
            "confidence": <0-100>,
            "reason": "<brief explanation>"
        }}
    ]
}}
"""


class MergeStats:
    """Statistics tracking for entity deduplication."""
    def __init__(self):
        self.total_entities: int = 0
        self.unique_entities: int = 0
        self.merges_by_method: Dict[str, int] = {}
        self.top_merged: List[Dict[str, Any]] = []
        self.relationships_before: int = 0
        self.relationships_after: int = 0
        self.relationships_removed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "unique_entities": self.unique_entities,
            "merges_by_method": self.merges_by_method,
            "top_merged": self.top_merged,
            "relationships_before": self.relationships_before,
            "relationships_after": self.relationships_after,
            "relationships_removed": self.relationships_removed,
        }


class ResolutionService:
    """
    Resolve and merge duplicate entities with relationship preservation.

    Multi-tier deduplication strategy:
    1. Alias dictionary (pre-loaded common aliases)
    2. Exact/fuzzy matching (normalization, substring, aliases)
    3. LLM batch confirmation (for ambiguous clusters)
    """

    # Merge methods for logging
    METHOD_ALIAS_DICT = "alias_dict"
    METHOD_EXACT_MATCH = "exact_match"
    METHOD_FUZZY_MATCH = "fuzzy_match"
    METHOD_LLM_BATCH = "llm_batch"

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or get_llm_client()

    async def resolve_entities(
        self,
        analysis_id: UUID,
        db: AsyncSession,
        use_llm: bool = True,
        min_confidence: int = 60,
    ) -> MergeStats:
        """
        Resolve duplicate entities for an analysis.

        Args:
            analysis_id: Analysis to process
            db: Database session
            use_llm: Whether to use LLM for merge confirmation
            min_confidence: Minimum confidence for auto-merge (0-100)

        Returns:
            MergeStats with deduplication results
        """
        stats = MergeStats()

        # Get all entities for analysis
        result = await db.execute(
            select(Entity)
            .where(Entity.analysis_id == analysis_id)
            .where(Entity.merged_into == None)
            .order_by(Entity.entity_type, Entity.label)
        )
        entities = result.scalars().all()
        stats.total_entities = len(entities)

        # Count relationships before
        rel_result = await db.execute(
            select(Relationship)
            .where(Relationship.analysis_id == analysis_id)
        )
        stats.relationships_before = len(rel_result.scalars().all())

        # Group by entity type (never merge across types)
        by_type: Dict[str, List[Entity]] = {}
        for entity in entities:
            by_type.setdefault(entity.entity_type, []).append(entity)

        # Process each entity type
        all_merges: List[Dict[str, Any]] = []

        for entity_type, type_entities in by_type.items():
            # Tier 1: Alias dictionary matching
            alias_groups = await self._group_by_alias_dictionary(type_entities, db, analysis_id)
            all_merges.extend(alias_groups)

            # Collect IDs that are already in alias groups
            merged_in_alias: Set[UUID] = set()
            for group in alias_groups:
                merged_in_alias.add(group["primary"].id)
                merged_in_alias.update(e.id for e in group["merged"])

            # Tier 1: Exact/fuzzy matching for remaining
            remaining = [e for e in type_entities if e.id not in merged_in_alias]
            fuzzy_groups = await self._group_by_fuzzy_match(remaining)
            all_merges.extend(fuzzy_groups)

        # Tier 3: LLM batch confirmation (optional)
        if use_llm:
            all_merges = await self._confirm_merges_with_llm(all_merges, min_confidence)

        # Execute merges with relationship remapping
        for merge_group in all_merges:
            if not merge_group.get("skip", False):
                await self._merge_with_relationships(
                    db,
                    merge_group["primary"],
                    merge_group["merged"],
                    merge_group["canonical_label"],
                    merge_group["method"],
                    merge_group.get("confidence", 100),
                    analysis_id,
                    stats,
                )

        # Mark remaining entities as resolved
        await db.execute(
            update(Entity)
            .where(Entity.analysis_id == analysis_id)
            .where(Entity.merged_into == None)
            .where(Entity.is_resolved == False)
            .values(is_resolved=True)
        )

        # Count relationships after
        rel_result = await db.execute(
            select(Relationship)
            .where(Relationship.analysis_id == analysis_id)
        )
        stats.relationships_after = len(rel_result.scalars().all())
        stats.relationships_removed = stats.relationships_before - stats.relationships_after
        stats.unique_entities = stats.total_entities - sum(
            len(g.get("merged", [])) for g in all_merges if not g.get("skip")
        )

        await db.commit()
        return stats

    async def _group_by_alias_dictionary(
        self,
        entities: List[Entity],
        db: AsyncSession,
        analysis_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Group entities using pre-loaded alias dictionary.

        Returns list of merge groups with method="alias_dict"
        """
        merge_groups: List[Dict[str, Any]] = []
        processed: Set[UUID] = set()

        for entity in entities:
            if entity.id in processed:
                continue

            canonical = get_canonical_label(entity.label, entity.entity_type)
            if not canonical:
                continue

            # Find all entities that match this canonical alias
            group: List[Entity] = [entity]
            processed.add(entity.id)

            for other in entities:
                if other.id in processed:
                    continue
                if is_alias_match(entity.label, other.label, entity.entity_type):
                    group.append(other)
                    processed.add(other.id)

            if len(group) > 1:
                # Select primary entity for this group
                primary = self._select_primary_entity(group)
                merged = [e for e in group if e.id != primary.id]

                merge_groups.append({
                    "primary": primary,
                    "merged": merged,
                    "canonical_label": canonical,
                    "method": self.METHOD_ALIAS_DICT,
                    "confidence": 100,
                })

        return merge_groups

    async def _group_by_fuzzy_match(
        self,
        entities: List[Entity],
    ) -> List[Dict[str, Any]]:
        """
        Group entities using exact/fuzzy matching.

        Methods:
        - Exact match after normalization
        - Substring match (with min length check)
        - Alias match from extracted aliases

        Returns list of merge groups
        """
        merge_groups: List[Dict[str, Any]] = []
        used = set()

        for i, entity in enumerate(entities):
            if i in used:
                continue

            group: List[Entity] = [entity]
            used.add(i)
            norm_label = self._normalize(entity.label)

            for j, other in enumerate(entities[i+1:], start=i+1):
                if j in used:
                    continue

                if self._is_similar(norm_label, self._normalize(other.label), entity, other):
                    group.append(other)
                    used.add(j)

            if len(group) > 1:
                primary = self._select_primary_entity(group)
                merged = [e for e in group if e.id != primary.id]
                method = self.METHOD_EXACT_MATCH if norm_label == self._normalize(primary.label) else self.METHOD_FUZZY_MATCH

                merge_groups.append({
                    "primary": primary,
                    "merged": merged,
                    "canonical_label": primary.label,
                    "method": method,
                    "confidence": 90 if method == self.METHOD_EXACT_MATCH else 75,
                })

        return merge_groups

    async def _confirm_merges_with_llm(
        self,
        merge_groups: List[Dict[str, Any]],
        min_confidence: int,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM batch confirmation for merge decisions.

        Groups below min_confidence are sent to LLM for confirmation.
        """
        # Filter groups needing LLM confirmation
        needs_confirmation = [
            (i, g) for i, g in enumerate(merge_groups)
            if g.get("confidence", 100) < min_confidence
        ]

        if not needs_confirmation:
            return merge_groups

        # Batch processing (20 groups at a time to avoid token limits)
        batch_size = 20
        for batch_start in range(0, len(needs_confirmation), batch_size):
            batch = needs_confirmation[batch_start:batch_start + batch_size]
            groups_text = self._format_groups_for_llm(batch)

            try:
                result = await self.llm.complete(
                    prompt=BATCH_MERGE_PROMPT.format(groups=groups_text),
                    schema={
                        "type": "object",
                        "properties": {
                            "decisions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "integer"},
                                        "should_merge": {"type": "boolean"},
                                        "canonical_label": {"type": "string"},
                                        "confidence": {"type": "integer"},
                                        "reason": {"type": "string"},
                                    },
                                    "required": ["group_id", "should_merge", "confidence", "reason"],
                                },
                            },
                        },
                        "required": ["decisions"],
                    },
                    temperature=0.0,
                )

                if isinstance(result, dict) and "decisions" in result:
                    for decision in result["decisions"]:
                        group_idx = decision.get("group_id")
                        if group_idx is not None and group_idx < len(batch):
                            original_idx, group = batch[group_idx]
                            if not decision.get("should_merge", False):
                                merge_groups[original_idx]["skip"] = True
                            elif decision.get("canonical_label"):
                                merge_groups[original_idx]["canonical_label"] = decision["canonical_label"]
                                merge_groups[original_idx]["confidence"] = decision.get("confidence", 95)
                                merge_groups[original_idx]["method"] = self.METHOD_LLM_BATCH

            except Exception as e:
                logger.warning(f"LLM batch confirmation failed: {e}")
                # Keep original decisions on failure

        return merge_groups

    def _format_groups_for_llm(self, batch: List[tuple[int, Dict[str, Any]]]) -> str:
        """Format merge groups for LLM batch processing."""
        lines = []
        for idx, (_, group) in enumerate(batch):
            lines.append(f"\nGroup {idx + 1}:")
            lines.append(f"  - {group['primary'].label} (confidence: {group['primary'].confidence})")
            for merged in group["merged"]:
                lines.append(f"  - {merged.label} (confidence: {merged.confidence})")
        return "\n".join(lines)

    def _select_primary_entity(self, entities: List[Entity]) -> Entity:
        """
        Select the primary entity from a merge group.

        Selection criteria in order:
        1. Full name preferred over abbreviation (longer label)
        2. Higher confidence score
        3. More provenance records (more sources)
        4. Most recently created
        """
        # Sort by multiple criteria
        sorted_entities = sorted(
            entities,
            key=lambda e: (
                len(e.label),  # Prefer longer (full) names
                e.confidence or 0,  # Higher confidence
                -1,  # Placeholder for provenance count (not available here)
            ),
            reverse=True,
        )
        return sorted_entities[0]

    def _normalize(self, label: str) -> str:
        """
        Normalize label for comparison.

        - Lowercase
        - Trim whitespace
        - Remove special characters (but keep spaces)
        - Remove common prefixes (the, a, an)
        """
        # Lowercase and trim
        normalized = label.lower().strip()

        # Remove special characters (keep letters, numbers, spaces)
        normalized = re.sub(r"[^\w\s]", "", normalized)

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        # Remove leading articles
        if normalized.startswith("the "):
            normalized = normalized[4:]
        elif normalized.startswith("a "):
            normalized = normalized[2:]
        elif normalized.startswith("an "):
            normalized = normalized[3:]

        return normalized.strip()

    def _is_similar(
        self,
        norm1: str,
        norm2: str,
        entity1: Entity,
        entity2: Entity,
    ) -> bool:
        """
        Check if two entities are similar using multiple methods.

        Returns True if entities should be merged.
        """
        # Exact match after normalization
        if norm1 == norm2:
            return True

        # One is contained in the other (substring match)
        # Require minimum length to avoid false positives on short words
        min_len = 4
        if len(norm1) >= min_len and len(norm2) >= min_len:
            if norm1 in norm2 or norm2 in norm1:
                return True

        # Check extracted aliases
        aliases1 = {a.lower() for a in (entity1.aliases or [])}
        aliases2 = {a.lower() for a in (entity2.aliases or [])}

        # Check if any alias matches
        if norm2 in aliases1 or norm1 in aliases2:
            return True

        # Check alias overlap
        if aliases1 & aliases2:  # Intersection not empty
            return True

        return False

    async def _merge_with_relationships(
        self,
        db: AsyncSession,
        primary: Entity,
        merged_entities: List[Entity],
        canonical_label: str,
        method: str,
        confidence: int,
        analysis_id: UUID,
        stats: MergeStats,
    ) -> None:
        """
        Merge entities into primary, preserving relationships.

        Critical: Remaps all relationships pointing to merged entities.
        """
        if not merged_entities:
            return

        merged_ids = [e.id for e in merged_entities]

        # Update primary entity
        primary.label = canonical_label
        primary.is_resolved = True
        primary.confidence = max([primary.confidence or 0] + [e.confidence or 0 for e in merged_entities])

        # Combine all aliases
        all_aliases = set(primary.aliases or [])
        for entity in merged_entities:
            all_aliases.add(entity.label)
            all_aliases.update(entity.aliases or [])
        all_aliases.discard(canonical_label)
        primary.aliases = list(all_aliases)

        # Get all relationships that need remapping
        for merged_entity in merged_entities:
            merged_id = merged_entity.id

            # Update relationships where merged entity is source
            await db.execute(
                update(Relationship)
                .where(Relationship.source_entity_id == merged_id)
                .where(Relationship.analysis_id == analysis_id)
                .values(source_entity_id=primary.id)
            )

            # Update relationships where merged entity is target
            await db.execute(
                update(Relationship)
                .where(Relationship.target_entity_id == merged_id)
                .where(Relationship.analysis_id == analysis_id)
                .values(target_entity_id=primary.id)
            )

            # Update provenance to point to primary
            await db.execute(
                update(EntityProvenance)
                .where(EntityProvenance.entity_id == merged_id)
                .values(entity_id=primary.id)
            )

            # Mark entity as merged
            merged_entity.merged_into = primary.id

        # Delete self-referential relationships (A -> A after merge)
        await db.execute(
            delete(Relationship)
            .where(Relationship.analysis_id == analysis_id)
            .where(Relationship.source_entity_id == primary.id)
            .where(Relationship.target_entity_id == primary.id)
        )

        # Combine duplicate relationships (same source, target, type)
        await self._deduplicate_relationships(db, primary.id, analysis_id)

        # Log merge in entity_merge_log
        merge_log = EntityMergeLog(
            id=uuid4(),
            analysis_id=analysis_id,
            primary_entity_id=primary.id,
            merged_entity_ids=merged_ids,
            merge_method=method,
            confidence=confidence,
            canonical_label=canonical_label,
        )
        db.add(merge_log)

        # Update stats
        stats.merges_by_method[method] = stats.merges_by_method.get(method, 0) + len(merged_entities)
        stats.top_merged.append({
            "canonical_label": canonical_label,
            "occurrence_count": len(merged_entities) + 1,
            "method": method,
        })

        # Sort top_merged and keep top 10
        stats.top_merged.sort(key=lambda x: x["occurrence_count"], reverse=True)
        stats.top_merged = stats.top_merged[:10]

    async def _deduplicate_relationships(
        self,
        db: AsyncSession,
        entity_id: UUID,
        analysis_id: UUID,
    ) -> None:
        """
        Combine duplicate relationships after entity merge.

        When A and B merge, if we have A->C and B->C, we now have two
        primary->C relationships. Combine them by keeping the one with
        higher confidence.
        """
        # Find all relationships for this entity as source
        result = await db.execute(
            select(Relationship)
            .where(Relationship.analysis_id == analysis_id)
            .where(Relationship.source_entity_id == entity_id)
        )
        relationships = result.scalars().all()

        # Group by (target, type)
        groups: Dict[tuple[UUID, str], List[Relationship]] = {}
        for rel in relationships:
            key = (rel.target_entity_id, rel.relationship_type)
            groups.setdefault(key, []).append(rel)

        # For each duplicate group, keep the one with highest confidence
        for key, dupes in groups.items():
            if len(dupes) > 1:
                # Sort by confidence descending
                dupes.sort(key=lambda r: r.confidence or 0, reverse=True)
                keeper = dupes[0]

                # Delete duplicates
                for dupe in dupes[1:]:
                    await db.execute(
                        delete(Relationship).where(Relationship.id == dupe.id)
                    )

                    # If keeper had lower confidence, update it
                    if dupe.confidence and (not keeper.confidence or dupe.confidence > keeper.confidence):
                        keeper.confidence = dupe.confidence
