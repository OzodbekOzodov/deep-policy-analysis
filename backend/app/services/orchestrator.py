"""Pipeline Orchestrator - Full Analysis Workflow"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, update

from app.models.database import AnalysisJob, Chunk, Entity, EntityProvenance, Relationship
from app.services.extraction import ExtractionService
from app.services.events import emit_event
from app.clients.llm import get_llm_client

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Orchestrates the full analysis workflow:
    1. Ingestion - Verify documents and chunks exist
    2. Extraction - Extract APOR entities from each chunk
    3. Complete - Mark analysis as done
    """
    
    def __init__(self, analysis_id: UUID, session_maker: async_sessionmaker):
        self.analysis_id = analysis_id
        self.session_maker = session_maker
        self.extraction = ExtractionService(get_llm_client())
    
    async def run(self) -> None:
        """Run the full pipeline."""
        try:
            await self._update_status("processing", "ingesting")
            await self._emit("stage_change", {"stage": "ingesting", "percent": 10})
            await self._run_ingestion()
            
            await self._update_status("processing", "extracting")
            await self._emit("stage_change", {"stage": "extracting", "percent": 30})
            await self._run_extraction()
            
            await self._update_status("complete", "complete")
            await self._emit("stage_change", {"stage": "complete", "percent": 100})
            await self._emit("done", {})
            
        except Exception as e:
            logger.error(f"Pipeline failed for {self.analysis_id}: {e}")
            await self._update_status("failed", "failed", str(e))
            await self._emit("error", {"message": str(e)})
    
    async def _run_ingestion(self) -> None:
        """Verify chunks exist for analysis."""
        async with self.session_maker() as db:
            result = await db.execute(
                select(Chunk).where(Chunk.analysis_id == self.analysis_id)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                logger.warning(f"No chunks found for analysis {self.analysis_id}")
            else:
                logger.info(f"Found {len(chunks)} chunks for analysis")
                await self._emit("stats_update", {"chunks": len(chunks)})
    
    async def _run_extraction(self) -> None:
        """Extract APOR entities from each chunk."""
        async with self.session_maker() as db:
            # Get pending chunks
            result = await db.execute(
                select(Chunk)
                .where(Chunk.analysis_id == self.analysis_id)
                .where(Chunk.extraction_status == "pending")
                .order_by(Chunk.sequence)
            )
            chunks = result.scalars().all()
            
            total_counts = {"actors": 0, "policies": 0, "outcomes": 0, "risks": 0}
            
            for i, chunk in enumerate(chunks):
                try:
                    # Extract entities from chunk
                    extraction_result = await self.extraction.extract_from_chunk(
                        chunk.content,
                        str(chunk.id)
                    )
                    
                    # Store entities
                    entity_id_map = {}  # temp_id -> real_id
                    
                    for entity_data in extraction_result.get("entities", []):
                        entity = Entity(
                            analysis_id=self.analysis_id,
                            entity_type=entity_data["type"],
                            label=entity_data["label"],
                            aliases=entity_data.get("aliases", []),
                            confidence=entity_data.get("confidence", 50),
                            impact_score=50,
                            summary=None,
                            is_resolved=False
                        )
                        db.add(entity)
                        await db.flush()
                        
                        entity_id_map[entity_data["temp_id"]] = entity.id
                        total_counts[entity_data["type"] + "s"] += 1
                        
                        # Add provenance
                        provenance = EntityProvenance(
                            entity_id=entity.id,
                            chunk_id=chunk.id,
                            quote=entity_data.get("quote", ""),
                            confidence=entity_data.get("confidence", 50)
                        )
                        db.add(provenance)
                    
                    # Store relationships  
                    for rel_data in extraction_result.get("relationships", []):
                        # Find entity IDs by label
                        source_entity = await self._find_entity_by_label(
                            db, rel_data["source"]
                        )
                        target_entity = await self._find_entity_by_label(
                            db, rel_data["target"]
                        )
                        
                        if source_entity and target_entity:
                            relationship = Relationship(
                                analysis_id=self.analysis_id,
                                source_entity_id=source_entity.id,
                                target_entity_id=target_entity.id,
                                relationship_type=rel_data["relationship"],
                                confidence=rel_data.get("confidence", 50)
                            )
                            db.add(relationship)
                    
                    # Mark chunk as processed
                    chunk.extraction_status = "complete"
                    chunk.extraction_result = extraction_result
                    
                    await db.commit()
                    
                    # Emit progress
                    percent = 30 + int((i + 1) / len(chunks) * 60)
                    await self._emit("stats_update", {
                        "stats": total_counts,
                        "percent": percent
                    })
                    
                except Exception as e:
                    logger.error(f"Extraction failed for chunk {chunk.id}: {e}")
                    chunk.extraction_status = "failed"
                    await db.commit()
            
            # Update analysis entity counts
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == self.analysis_id)
                .values(entities_count=total_counts)
            )
            await db.commit()
    
    async def _find_entity_by_label(
        self, 
        db: AsyncSession, 
        label: str
    ) -> Optional[Entity]:
        """Find entity by label in current analysis."""
        result = await db.execute(
            select(Entity)
            .where(Entity.analysis_id == self.analysis_id)
            .where(Entity.label == label)
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _update_status(
        self, 
        status: str, 
        stage: str, 
        error: Optional[str] = None
    ) -> None:
        """Update analysis status."""
        async with self.session_maker() as db:
            values = {
                "status": status,
                "current_stage": stage,
                "updated_at": datetime.utcnow()
            }
            if error:
                values["error_message"] = error
            if status == "complete":
                values["completed_at"] = datetime.utcnow()
            
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == self.analysis_id)
                .values(**values)
            )
            await db.commit()
    
    async def _emit(self, event_type: str, data: dict) -> None:
        """Emit progress event."""
        async with self.session_maker() as db:
            await emit_event(db, self.analysis_id, event_type, data)


async def run_pipeline(analysis_id: str, session_maker: async_sessionmaker) -> None:
    """Convenience function to run pipeline."""
    pipeline = AnalysisPipeline(UUID(analysis_id), session_maker)
    await pipeline.run()
