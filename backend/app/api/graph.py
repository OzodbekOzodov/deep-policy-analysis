"""Graph API Routes - Real Implementation"""

from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db
from app.models.schemas import (
    GraphResponse, 
    EntityResponse, 
    RelationshipResponse, 
    ProvenanceResponse
)
from app.models.database import (
    AnalysisJob,
    Entity, 
    Relationship, 
    EntityProvenance,
    Checkpoint
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{analysis_id}", response_model=GraphResponse)
async def get_graph(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get APOR graph for analysis.
    
    Returns all resolved entities and their relationships.
    """
    # Verify analysis exists
    analysis = await db.get(AnalysisJob, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get entities (non-merged ones)
    entity_result = await db.execute(
        select(Entity)
        .where(Entity.analysis_id == analysis_id)
        .where(Entity.merged_into == None)  # Only non-merged entities
        .order_by(Entity.created_at)
    )
    entities = entity_result.scalars().all()
    
    # Build entity responses with provenance
    nodes = []
    for entity in entities:
        # Get provenance for this entity
        prov_result = await db.execute(
            select(EntityProvenance)
            .where(EntityProvenance.entity_id == entity.id)
        )
        provenances = prov_result.scalars().all()
        
        nodes.append(EntityResponse(
            id=entity.id,
            type=entity.entity_type,
            label=entity.label,
            confidence=entity.confidence,
            impact_score=entity.impact_score,
            summary=entity.summary,
            provenance=[
                ProvenanceResponse(
                    chunk_id=p.chunk_id,
                    quote=p.quote,
                    confidence=p.confidence
                )
                for p in provenances
            ]
        ))
    
    # Get relationships
    rel_result = await db.execute(
        select(Relationship)
        .where(Relationship.analysis_id == analysis_id)
    )
    relationships = rel_result.scalars().all()
    
    links = [
        RelationshipResponse(
            id=rel.id,
            source=rel.source_entity_id,
            target=rel.target_entity_id,
            relationship=rel.relationship_type,
            confidence=rel.confidence
        )
        for rel in relationships
    ]
    
    # Get version from checkpoints count
    version_result = await db.execute(
        select(func.count())
        .select_from(Checkpoint)
        .where(Checkpoint.analysis_id == analysis_id)
    )
    version = version_result.scalar() or 1
    
    return GraphResponse(
        nodes=nodes,
        links=links,
        version=version,
        summary=analysis.summary,
        projected_gdp=analysis.projected_gdp,
        social_stability=analysis.social_stability,
        timeline_labels=analysis.timeline_labels
    )
