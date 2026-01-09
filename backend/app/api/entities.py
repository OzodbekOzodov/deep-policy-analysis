"""Entity Detail API Routes - Connections and Analysis Summary"""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.api.deps import get_db
from app.models.schemas import (
    EntityConnectionsResponse,
    ConnectedEntityInfo,
    EntityConnectionsByType,
    AnalysisSummaryRequest,
    AnalysisSummaryResponse,
    CitationItem,
)
from app.models.database import (
    Entity,
    Relationship,
    EntityProvenance,
    Chunk,
    Document,
    SummaryCache,
)

router = APIRouter(prefix="/api/entities", tags=["entities"])
logger = logging.getLogger(__name__)


def _get_plural_type(entity_type: str) -> str:
    """Convert entity type to plural form for dictionary keys."""
    return f"{entity_type}s"


@router.get("/{entity_id}/connections", response_model=EntityConnectionsResponse)
async def get_entity_connections(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all connections for an entity, grouped by APOR type.

    Returns both counts and detailed entity information for all connected entities.
    """
    # Get the focus entity
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get all relationships where this entity is source OR target
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

    # Group connected entities by type
    connections = {
        "actors": EntityConnectionsByType(),
        "policies": EntityConnectionsByType(),
        "outcomes": EntityConnectionsByType(),
        "risks": EntityConnectionsByType(),
    }

    for rel in relationships:
        # Determine the connected entity (the one that's not our focus entity)
        connected_entity_id = (
            rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
        )

        connected_entity = await db.get(Entity, connected_entity_id)
        if not connected_entity or connected_entity.merged_into is not None:
            continue  # Skip merged entities

        # Build connected entity info
        entity_info = ConnectedEntityInfo(
            id=connected_entity.id,
            label=connected_entity.label,
            type=connected_entity.entity_type,
            relationship_type=rel.relationship_type,
            confidence=rel.confidence or 50
        )

        plural_type = _get_plural_type(connected_entity.entity_type)
        if plural_type in connections:
            connections[plural_type].entities.append(entity_info)
            connections[plural_type].count += 1

    return EntityConnectionsResponse(
        entity_id=entity.id,
        entity_label=entity.label,
        entity_type=entity.entity_type,
        connections=connections
    )


@router.post("/{entity_id}/summary", response_model=AnalysisSummaryResponse)
async def generate_entity_summary(
    entity_id: UUID,
    request: AnalysisSummaryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate an analysis summary for an entity with selected connection types.

    Uses LLM to generate a narrative with clickable citations.
    Results are cached by entity_id + config_hash.
    """
    # Verify entity exists
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Create cache key from entity_id + sorted selected_types + analysis_id
    config_str = ",".join(sorted(request.selected_types))
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()
    cache_key = hashlib.sha256(f"{entity_id}:{config_hash}:{request.analysis_id}".encode()).hexdigest()

    # Check cache first
    cached = await db.execute(
        select(SummaryCache).where(SummaryCache.cache_key == cache_key)
    )
    cached_summary = cached.scalar_one_or_none()

    if cached_summary:
        logger.info(f"Returning cached summary for entity {entity_id}")
        return AnalysisSummaryResponse(
            entity_id=entity_id,
            entity_label=entity.label,
            summary=cached_summary.summary,
            citations=json.loads(cached_summary.citations) if isinstance(cached_summary.citations, str) else cached_summary.citations,
            cache_key=cache_key
        )

    # Not cached - generate new summary
    from app.services.summary_generator import generate_entity_summary as generate_summary

    try:
        summary_text, citations = await generate_summary(
            db=db,
            entity=entity,
            selected_types=request.selected_types,
            analysis_id=request.analysis_id
        )

        # Cache the result
        cache_entry = SummaryCache(
            cache_key=cache_key,
            entity_id=entity_id,
            analysis_id=request.analysis_id,
            config_hash=config_hash,
            summary=summary_text,
            citations=json.dumps([c.model_dump() for c in citations]) if citations else []
        )
        db.add(cache_entry)
        await db.commit()

        return AnalysisSummaryResponse(
            entity_id=entity_id,
            entity_label=entity.label,
            summary=summary_text,
            citations=citations,
            cache_key=cache_key
        )

    except Exception as e:
        logger.error(f"Failed to generate summary for entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.get("/{entity_id}/provenance")
async def get_entity_provenance(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get full provenance details for an entity with chunk content.
    Used by the citation popover to display source text.
    """
    # Verify entity exists
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get all provenance with chunk details
    prov_result = await db.execute(
        select(EntityProvenance, Chunk, Document)
        .join(Chunk, EntityProvenance.chunk_id == Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(EntityProvenance.entity_id == entity_id)
    )
    provenance_records = prov_result.all()

    provenance_details = []
    for prov, chunk, document in provenance_records:
        provenance_details.append({
            "chunk_id": prov.chunk_id,
            "quote": prov.quote,
            "confidence": prov.confidence or 50,
            "chunk_content": chunk.content,
            "document_title": document.title or "Untitled Document",
            "document_id": document.id
        })

    return {
        "entity_id": entity_id,
        "entity_label": entity.label,
        "provenance": provenance_details
    }
