"""Entity Resolution Service - Merge Duplicate Entities"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.database import Entity, EntityProvenance
from app.clients.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


MERGE_CONFIRMATION_PROMPT = """Are these different references to the SAME real-world entity?

Entities:
{entities}

Consider:
- Abbreviations/acronyms (e.g., "Ministry of Defense" and "MoD")
- Variations in naming (e.g., "US Congress" and "United States Congress")
- Context clues from the quotes

Answer in JSON format:
{{"should_merge": true/false, "reason": "brief explanation", "canonical_label": "preferred name if merging"}}
"""


class ResolutionService:
    """
    Resolve and merge duplicate entities.
    
    Uses simple text similarity and optional LLM confirmation
    to identify entities that refer to the same real-world thing.
    """
    
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or get_llm_client()
    
    async def resolve_entities(
        self, 
        analysis_id: UUID, 
        db: AsyncSession,
        use_llm: bool = False
    ) -> int:
        """
        Resolve duplicate entities for an analysis.
        
        Args:
            analysis_id: Analysis to process
            db: Database session
            use_llm: Whether to use LLM for merge confirmation
            
        Returns:
            Number of entities merged
        """
        # Get all entities for analysis
        result = await db.execute(
            select(Entity)
            .where(Entity.analysis_id == analysis_id)
            .where(Entity.merged_into == None)
            .order_by(Entity.entity_type, Entity.label)
        )
        entities = result.scalars().all()
        
        # Group by type
        by_type: Dict[str, List[Entity]] = {}
        for entity in entities:
            by_type.setdefault(entity.entity_type, []).append(entity)
        
        merge_count = 0
        
        # Find similar entities within each type
        for entity_type, type_entities in by_type.items():
            # Group by normalized label
            groups = self._group_similar(type_entities)
            
            for group in groups:
                if len(group) < 2:
                    continue
                
                # Determine if should merge
                should_merge = True
                canonical_label = group[0].label
                
                if use_llm and len(group) <= 5:  # Only use LLM for small groups
                    try:
                        merge_decision = await self._check_merge_with_llm(group)
                        should_merge = merge_decision.get("should_merge", True)
                        if should_merge and merge_decision.get("canonical_label"):
                            canonical_label = merge_decision["canonical_label"]
                    except Exception as e:
                        logger.warning(f"LLM merge check failed: {e}")
                
                if should_merge:
                    merged = await self._merge_entities(db, group, canonical_label)
                    merge_count += merged
        
        # Mark remaining entities as resolved
        await db.execute(
            update(Entity)
            .where(Entity.analysis_id == analysis_id)
            .where(Entity.merged_into == None)
            .where(Entity.is_resolved == False)
            .values(is_resolved=True)
        )
        await db.commit()
        
        return merge_count
    
    def _group_similar(self, entities: List[Entity]) -> List[List[Entity]]:
        """Group entities with similar labels."""
        groups: List[List[Entity]] = []
        used = set()
        
        for i, entity in enumerate(entities):
            if i in used:
                continue
            
            group = [entity]
            used.add(i)
            norm_label = self._normalize(entity.label)
            
            for j, other in enumerate(entities[i+1:], start=i+1):
                if j in used:
                    continue
                
                other_norm = self._normalize(other.label)
                
                # Check similarity
                if self._is_similar(norm_label, other_norm, entity, other):
                    group.append(other)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def _normalize(self, label: str) -> str:
        """Normalize label for comparison."""
        return label.lower().strip()
    
    def _is_similar(
        self, 
        norm1: str, 
        norm2: str, 
        entity1: Entity, 
        entity2: Entity
    ) -> bool:
        """Check if two entities are similar."""
        # Exact match
        if norm1 == norm2:
            return True
        
        # One is contained in the other
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Check aliases
        aliases1 = [a.lower() for a in (entity1.aliases or [])]
        aliases2 = [a.lower() for a in (entity2.aliases or [])]
        
        if norm2 in aliases1 or norm1 in aliases2:
            return True
        
        return False
    
    async def _check_merge_with_llm(self, entities: List[Entity]) -> Dict:
        """Use LLM to confirm entity merge."""
        entities_text = "\n".join([
            f"- {e.label} (confidence: {e.confidence})"
            for e in entities
        ])
        
        prompt = MERGE_CONFIRMATION_PROMPT.format(entities=entities_text)
        
        result = await self.llm.complete(
            prompt=prompt,
            schema={
                "type": "object",
                "properties": {
                    "should_merge": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "canonical_label": {"type": "string"}
                },
                "required": ["should_merge", "reason"]
            },
            temperature=0.0
        )
        
        return result if isinstance(result, dict) else {}
    
    async def _merge_entities(
        self, 
        db: AsyncSession, 
        entities: List[Entity],
        canonical_label: str
    ) -> int:
        """Merge entities into the first one."""
        if len(entities) < 2:
            return 0
        
        primary = entities[0]
        
        # Update primary entity
        primary.label = canonical_label
        primary.is_resolved = True
        
        # Combine confidence (max)
        primary.confidence = max(e.confidence for e in entities)
        
        # Combine aliases
        all_aliases = set(primary.aliases or [])
        for entity in entities[1:]:
            all_aliases.add(entity.label)
            all_aliases.update(entity.aliases or [])
        all_aliases.discard(canonical_label)
        primary.aliases = list(all_aliases)
        
        # Merge provenance from other entities
        for entity in entities[1:]:
            # Update provenance to point to primary
            await db.execute(
                update(EntityProvenance)
                .where(EntityProvenance.entity_id == entity.id)
                .values(entity_id=primary.id)
            )
            
            # Mark entity as merged
            entity.merged_into = primary.id
        
        await db.commit()
        return len(entities) - 1
