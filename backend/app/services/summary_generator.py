"""Entity Analysis Summary Generator - LLM Service"""

import logging
from typing import List, Tuple, NamedTuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.clients.llm import LLMClient
from app.models.database import (
    Entity,
    Relationship,
    EntityProvenance,
    Chunk,
    Document,
)
from app.models.schemas import CitationItem

logger = logging.getLogger(__name__)


def _get_plural_type(entity_type: str) -> str:
    """Convert entity type to plural form."""
    return f"{entity_type}s"


class PromptData(NamedTuple):
    """Container for prompt string and associated metadata."""
    prompt: str
    citation_map: dict
    provenance_map: dict


async def generate_entity_summary(
    db: AsyncSession,
    entity: Entity,
    selected_types: List[str],
    analysis_id: UUID
) -> Tuple[str, List[CitationItem]]:
    """
    Generate an analytical summary for an entity with selected connection types.

    Returns:
        Tuple of (summary_text with citation markers, list of CitationItem objects)
    """
    llm = LLMClient()

    try:
        # 1. Fetch connected entities based on selected types
        connected_entities, relationships_map = await _fetch_connected_entities(
            db, entity.id, selected_types
        )

        if not connected_entities:
            return f"No connections found for {entity.label} with the selected types.", []

        # 2. Fetch provenance (source evidence) for all entities
        provenance_map = await _fetch_provenance_for_entities(
            db, [entity.id] + [e["id"] for e in connected_entities]
        )

        # 3. Build the LLM prompt
        prompt_data = _build_summary_prompt(
            focus_entity=entity,
            connected_entities=connected_entities,
            relationships_map=relationships_map,
            provenance_map=provenance_map
        )

        # 4. Call LLM
        logger.info(f"Generating summary for entity {entity.label} with {len(connected_entities)} connections")
        response = await llm.complete(
            prompt=prompt_data.prompt,
            task="entity_analysis_summary",
            temperature=0.3,
            max_tokens=1500
        )

        # 5. Parse LLM response and build citations
        summary_text, citations = _parse_llm_response(response, prompt_data.citation_map, prompt_data.provenance_map)

        return summary_text, citations

    finally:
        await llm.close()


async def _fetch_connected_entities(
    db: AsyncSession,
    entity_id: UUID,
    selected_types: List[str]
) -> Tuple[List[dict], dict]:
    """
    Fetch connected entities filtered by selected types.

    selected_types may be in singular form (actor, policy) or plural (actors, policies).

    Returns:
        Tuple of (list of connected entity dicts, mapping of entity_id -> relationship info)
    """
    # Normalize selected_types to plural for consistent comparison
    selected_types_plural = set()
    for t in selected_types:
        if t.endswith('s'):
            selected_types_plural.add(t)  # Already plural
        else:
            selected_types_plural.add(f"{t}s")  # Convert to plural

    logger.info(f"Fetching connected entities for {entity_id}, selected_types (normalized): {selected_types_plural}")

    # Get relationships where this entity is source OR target
    relationships_result = await db.execute(
        select(Relationship)
        .where(
            or_(
                Relationship.source_entity_id == entity_id,
                Relationship.target_entity_id == entity_id
            )
        )
    )
    relationships = relationships_result.scalars().all()

    connected_entities = []
    relationships_map = {}  # entity_id -> relationship info

    for rel in relationships:
        # Determine connected entity
        connected_id = (
            rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
        )

        connected_entity = await db.get(Entity, connected_id)
        if not connected_entity or connected_entity.merged_into is not None:
            continue

        plural_type = _get_plural_type(connected_entity.entity_type)

        # Filter by selected types (now both in plural form)
        if plural_type not in selected_types_plural:
            logger.debug(f"Skipping {connected_entity.label} (type: {plural_type}) not in selected: {selected_types_plural}")
            continue

        entity_info = {
            "id": str(connected_entity.id),
            "label": connected_entity.label,
            "type": connected_entity.entity_type,
            "relationship_type": rel.relationship_type,
            "confidence": rel.confidence or 50,
            "summary": connected_entity.summary or ""
        }

        connected_entities.append(entity_info)
        relationships_map[str(connected_entity.id)] = {
            "relationship_type": rel.relationship_type,
            "confidence": rel.confidence or 50
        }

    logger.info(f"Found {len(connected_entities)} connected entities matching selected types")
    return connected_entities, relationships_map


async def _fetch_provenance_for_entities(
    db: AsyncSession,
    entity_ids: List[UUID]
) -> dict:
    """
    Fetch provenance (source chunks) for entities.

    Returns:
        Mapping of entity_id -> list of provenance records with chunk details
    """
    entity_ids_str = [str(eid) for eid in entity_ids]

    prov_result = await db.execute(
        select(EntityProvenance, Chunk, Document)
        .join(Chunk, EntityProvenance.chunk_id == Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(EntityProvenance.entity_id.in_(entity_ids_str))
    )

    provenance_map = {str(eid): [] for eid in entity_ids}

    for prov, chunk, document in prov_result.all():
        entity_id_str = str(prov.entity_id)
        provenance_map[entity_id_str].append({
            "chunk_id": str(prov.chunk_id),
            "quote": prov.quote,
            "confidence": prov.confidence or 50,
            "chunk_content": chunk.content,
            "document_title": document.title or "Untitled Document"
        })

    return provenance_map


def _build_summary_prompt(
    focus_entity: Entity,
    connected_entities: List[dict],
    relationships_map: dict,
    provenance_map: dict
) -> PromptData:
    """
    Build LLM prompt for entity summary generation.

    Citation numbers are assigned sequentially based on available provenance.

    Returns:
        PromptData containing prompt string and metadata for citation parsing
    """
    # Start building source evidence section with citation numbers
    citation_counter = 1
    source_evidence = []
    entity_citation_map = {}  # entity_id -> list of citation numbers

    # Add focus entity provenance
    focus_entity_id = str(focus_entity.id)
    if focus_entity_id in provenance_map and provenance_map[focus_entity_id]:
        entity_citation_map[focus_entity_id] = []

        for prov in provenance_map[focus_entity_id][:3]:  # Max 3 citations per entity
            citation_num = citation_counter
            citation_counter += 1

            entity_citation_map[focus_entity_id].append(citation_num)
            source_evidence.append(
                f"[{citation_num}] \"{prov['quote']}\" - {prov['document_title']}"
            )

    # Add connected entity provenance
    for entity_info in connected_entities:
        entity_id = entity_info["id"]
        if entity_id in provenance_map and provenance_map[entity_id]:
            entity_citation_map[entity_id] = []

            for prov in provenance_map[entity_id][:2]:  # Max 2 citations per related entity
                citation_num = citation_counter
                citation_counter += 1

                entity_citation_map[entity_id].append(citation_num)
                source_evidence.append(
                    f"[{citation_num}] \"{prov['quote']}\" - {prov['document_title']}"
                )

    # Build connected entities section with citation markers
    connected_entities_text = []
    for entity_info in connected_entities:
        entity_id = entity_info["id"]
        label = entity_info["label"]
        rel_type = entity_info["relationship_type"]

        # Get citation numbers for this entity
        citations = entity_citation_map.get(entity_id, [])
        citation_marker = " ".join([f"[{c}]" for c in citations]) if citations else ""

        connected_entities_text.append(
            f"- {label} (relationship: {rel_type}) {citation_marker}"
        )

    # Assemble full prompt
    prompt_text = f"""You are a policy analyst. Generate a 2-3 paragraph analytical summary.

FOCUS ENTITY: {focus_entity.label} ({focus_entity.entity_type})

CONNECTED ENTITIES (per user selection):
{chr(10).join(connected_entities_text)}

SOURCE EVIDENCE:
{chr(10).join(source_evidence)}

INSTRUCTIONS:
- Explain the relationships between {focus_entity.label} and the connected entities
- Use citation markers [1], [2], [3] to reference source evidence
- Write in formal analytical tone suitable for policy analysts
- Start with "Analysis indicates..." or similar neutral phrasing
- Each entity mention should cite its source evidence
- Keep the summary to approximately 200-300 words

Generate the summary now:"""

    return PromptData(
        prompt=prompt_text,
        citation_map=entity_citation_map,
        provenance_map=provenance_map
    )


def _parse_llm_response(
    response: str,
    citation_map: dict,
    provenance_map: dict
) -> Tuple[str, List[CitationItem]]:
    """
    Parse LLM response and build citation objects.

    Extracts citation numbers from the text and maps them to source chunks.
    """
    import re

    # Find all citation markers in the response
    citation_pattern = r"\[(\d+)\]"
    citation_numbers = set(int(m) for m in re.findall(citation_pattern, response))

    citations = []
    citation_chunk_map = {}  # citation_number -> (entity_id, quote, document_title, chunk_id)

    # Build citation mapping from provenance
    citation_counter = 1
    for entity_id, prov_list in provenance_map.items():
        for prov in prov_list:
            if citation_counter in citation_numbers:
                citation_chunk_map[citation_counter] = {
                    "entity_id": entity_id,
                    "quote": prov["quote"],
                    "document_title": prov["document_title"],
                    "chunk_id": prov["chunk_id"],
                    "confidence": prov["confidence"]
                }
            citation_counter += 1

    # Create CitationItem objects for citations found in response
    for citation_num in sorted(citation_numbers):
        if citation_num in citation_chunk_map:
            chunk_info = citation_chunk_map[citation_num]
            citations.append(CitationItem(
                id=citation_num,
                text=chunk_info["quote"],
                chunk_id=UUID(chunk_info["chunk_id"]),
                document_title=chunk_info["document_title"],
                relationship="entity_mention" if chunk_info["entity_id"] != "focus" else "focus_entity",
                confidence=chunk_info["confidence"]
            ))

    return response, citations
