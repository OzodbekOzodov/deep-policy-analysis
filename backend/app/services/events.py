"""Progress Events Service"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import ProgressEvent, AnalysisJob


async def emit_event(
    db: AsyncSession,
    analysis_id: UUID,
    event_type: str,
    data: dict
) -> None:
    """
    Emit a progress event for an analysis.
    
    Events are stored in the database and can be streamed via SSE.
    """
    event = ProgressEvent(
        analysis_id=analysis_id,
        event_type=event_type,
        data=data
    )
    db.add(event)
    await db.commit()


async def get_events_since(
    db: AsyncSession,
    analysis_id: UUID,
    last_id: int = 0
) -> list[ProgressEvent]:
    """Get all events since a given ID."""
    result = await db.execute(
        select(ProgressEvent)
        .where(ProgressEvent.analysis_id == analysis_id)
        .where(ProgressEvent.id > last_id)
        .order_by(ProgressEvent.id)
    )
    return result.scalars().all()


async def get_analysis_status(
    db: AsyncSession,
    analysis_id: UUID
) -> Optional[str]:
    """Get current analysis status."""
    analysis = await db.get(AnalysisJob, analysis_id)
    return analysis.status if analysis else None
