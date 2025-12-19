"""SSE (Server-Sent Events) API Routes - Real Implementation"""

from __future__ import annotations

import json
import asyncio
from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, async_session_maker
from app.services.events import get_events_since, get_analysis_status

router = APIRouter(prefix="/api/stream", tags=["streaming"])


@router.get("/{analysis_id}")
async def stream_progress(analysis_id: UUID):
    """
    Stream analysis progress via Server-Sent Events.

    Events include:
    - stage_change: Pipeline stage transitions
    - stats_update: APOR entity count updates
    - done: Analysis complete
    - error: Analysis failed
    """

    async def generate_events():
        # Send connected event
        yield f"data: {json.dumps({'type': 'connected', 'analysis_id': str(analysis_id)})}\n\n"

        last_id = 0
        retry_count = 0
        max_retries = 300  # 5 minutes at 1 second intervals

        try:
            while retry_count < max_retries:
                async with async_session_maker() as db:
                    # Get new events
                    events = await get_events_since(db, analysis_id, last_id)

                    for event in events:
                        event_data = {
                            "type": event.event_type,
                            **event.data
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_id = event.id

                    # Check if analysis is complete
                    status = await get_analysis_status(db, analysis_id)
                    if status in ("complete", "failed"):
                        if status == "complete":
                            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'error', 'message': 'Analysis failed'})}\n\n"
                        break

                # Wait before checking again
                await asyncio.sleep(0.5)
                retry_count += 1

            # Timeout - send done event
            if retry_count >= max_retries:
                yield f"data: {json.dumps({'type': 'timeout'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
