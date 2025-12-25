"""Analysis API Routes - Real Implementation"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db
from app.models.schemas import (
    CreateAnalysisRequest,
    AnalysisResponse,
    AnalysisProgress,
    APORCounts,
    CheckpointResponse,
)
from app.models.database import AnalysisJob, Document, Chunk, Checkpoint
from app.services.ingestion import ChunkingService

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)


# Background task runners (to be implemented in orchestrator)
_background_tasks: dict[UUID, asyncio.Task] = {}


@router.post("/", response_model=AnalysisResponse)
async def create_analysis(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new analysis job.
    
    If text_input is provided, creates a document and chunks automatically.
    Returns immediately; processing happens in background.
    """
    # Create analysis job
    analysis = AnalysisJob(
        query=request.query,
        scope=request.scope,
        depth=request.depth,
        status="created",
        current_stage="created"
    )
    db.add(analysis)
    await db.flush()
    
    # If text input provided, create document and chunks
    if request.text_input:
        document = Document(
            analysis_id=analysis.id,
            title=f"Input for: {request.query[:50]}...",
            content_type="text/plain",
            raw_content=request.text_input
        )
        db.add(document)
        await db.flush()
        
        # Chunk the text
        chunker = ChunkingService()
        chunk_data = chunker.chunk_text(request.text_input)
        
        for chunk_info in chunk_data:
            chunk = Chunk(
                document_id=document.id,
                analysis_id=analysis.id,
                sequence=chunk_info["sequence"],
                content=chunk_info["content"],
                token_count=chunk_info["token_count"],
                extraction_status="pending"
            )
            db.add(chunk)
    
    await db.commit()
    await db.refresh(analysis)
    
    # Start background processing using the real orchestrator pipeline
    background_tasks.add_task(run_analysis_pipeline_task, str(analysis.id))
    
    return AnalysisResponse(
        id=analysis.id,
        query=analysis.query,
        status=analysis.status,
        depth=analysis.depth or "standard",
        current_stage=analysis.current_stage,
        progress=AnalysisProgress(
            stage=analysis.current_stage or "created",
            percent=0,
            stats=APORCounts()
        ),
        created_at=analysis.created_at
    )


async def run_analysis_pipeline_task(analysis_id: str):
    """
    Background task to run the real analysis pipeline.
    """
    from app.api.deps import async_session_maker
    from app.services.orchestrator import run_pipeline

    try:
        # Run the real orchestrator pipeline
        await run_pipeline(analysis_id, async_session_maker)
    except Exception as e:
        logger.error(f"Pipeline task failed for {analysis_id}: {e}")


@router.get("", response_model=List[AnalysisResponse])
async def list_analyses(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of analyses to return"),
    offset: int = Query(0, ge=0, description="Number of analyses to skip"),
    status: Optional[str] = Query(None, description="Filter by status (e.g., 'complete', 'processing', 'failed')"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all analysis jobs with pagination and optional status filtering.
    Returns most recent analyses first.
    """
    query = select(AnalysisJob).order_by(AnalysisJob.created_at.desc())

    # Apply status filter if provided
    if status:
        query = query.where(AnalysisJob.status == status)

    # Apply pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    analyses = result.scalars().all()

    # Convert to response format
    responses = []
    for analysis in analyses:
        counts = analysis.entities_count or {}
        responses.append(
            AnalysisResponse(
                id=analysis.id,
                query=analysis.query,
                status=analysis.status,
                depth=analysis.depth or "standard",
                current_stage=analysis.current_stage,
                progress=AnalysisProgress(
                    stage=analysis.current_stage or "unknown",
                    percent=_stage_to_percent(analysis.current_stage),
                    stats=APORCounts(
                        actors=counts.get("actors", 0),
                        policies=counts.get("policies", 0),
                        outcomes=counts.get("outcomes", 0),
                        risks=counts.get("risks", 0)
                    )
                ),
                created_at=analysis.created_at,
                completed_at=analysis.completed_at
            )
        )

    return responses


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get analysis job status."""
    analysis = await db.get(AnalysisJob, analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Parse entities_count
    counts = analysis.entities_count or {}
    
    return AnalysisResponse(
        id=analysis.id,
        query=analysis.query,
        status=analysis.status,
        depth=analysis.depth or "standard",
        current_stage=analysis.current_stage,
        progress=AnalysisProgress(
            stage=analysis.current_stage or "unknown",
            percent=_stage_to_percent(analysis.current_stage),
            stats=APORCounts(
                actors=counts.get("actors", 0),
                policies=counts.get("policies", 0),
                outcomes=counts.get("outcomes", 0),
                risks=counts.get("risks", 0)
            )
        ),
        created_at=analysis.created_at,
        completed_at=analysis.completed_at
    )


@router.get("/{analysis_id}/checkpoints", response_model=list[CheckpointResponse])
async def get_checkpoints(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get analysis checkpoints."""
    result = await db.execute(
        select(Checkpoint)
        .where(Checkpoint.analysis_id == analysis_id)
        .order_by(Checkpoint.version)
    )
    checkpoints = result.scalars().all()
    
    return [
        CheckpointResponse(
            id=cp.id,
            stage=cp.stage,
            version=cp.version,
            stats=APORCounts(**cp.stats) if cp.stats else APORCounts(),
            created_at=cp.created_at
        )
        for cp in checkpoints
    ]


@router.get("/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get analysis report (stub)."""
    analysis = await db.get(AnalysisJob, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Stub: Return placeholder report structure
    return {"status": "not_generated", "analysis_id": str(analysis_id)}


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete an analysis job and all related data."""
    analysis = await db.get(AnalysisJob, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await db.delete(analysis)
    await db.commit()
    return None


def _stage_to_percent(stage: Optional[str]) -> int:
    """Convert stage name to approximate completion percentage."""
    stage_percents = {
        "created": 0,
        "ingesting": 10,
        "extracting": 40,
        "resolving": 70,
        "complete": 100,
        "failed": 0
    }
    return stage_percents.get(stage or "unknown", 0)
