"""Checkpoint Service - Save Pipeline State"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Checkpoint, Entity


class CheckpointService:
    """
    Save and retrieve pipeline state snapshots.
    """
    
    async def save_checkpoint(
        self,
        analysis_id: UUID,
        stage: str,
        db: AsyncSession
    ) -> UUID:
        """
        Save a checkpoint for the current pipeline state.
        
        Args:
            analysis_id: Analysis being processed
            stage: Current pipeline stage
            db: Database session
            
        Returns:
            Checkpoint ID
        """
        # Get current entity counts
        stats = await self._get_entity_counts(analysis_id, db)
        
        # Get next version number
        version_result = await db.execute(
            select(func.count())
            .select_from(Checkpoint)
            .where(Checkpoint.analysis_id == analysis_id)
        )
        version = (version_result.scalar() or 0) + 1
        
        # Create checkpoint
        checkpoint = Checkpoint(
            analysis_id=analysis_id,
            stage=stage,
            version=version,
            stats=stats,
            graph_snapshot=None  # Can be reconstructed from entities
        )
        db.add(checkpoint)
        await db.commit()
        await db.refresh(checkpoint)
        
        return checkpoint.id
    
    async def list_checkpoints(
        self,
        analysis_id: UUID,
        db: AsyncSession
    ) -> List[Dict]:
        """List all checkpoints for an analysis."""
        result = await db.execute(
            select(Checkpoint)
            .where(Checkpoint.analysis_id == analysis_id)
            .order_by(Checkpoint.version)
        )
        checkpoints = result.scalars().all()
        
        return [
            {
                "id": str(cp.id),
                "stage": cp.stage,
                "version": cp.version,
                "stats": cp.stats,
                "created_at": cp.created_at.isoformat() if cp.created_at else None
            }
            for cp in checkpoints
        ]
    
    async def _get_entity_counts(
        self,
        analysis_id: UUID,
        db: AsyncSession
    ) -> Dict[str, int]:
        """Get current entity counts by type."""
        result = await db.execute(
            select(Entity.entity_type, func.count())
            .where(Entity.analysis_id == analysis_id)
            .where(Entity.merged_into == None)
            .group_by(Entity.entity_type)
        )
        rows = result.all()
        
        counts = {"actors": 0, "policies": 0, "outcomes": 0, "risks": 0}
        for entity_type, count in rows:
            key = entity_type + "s" if not entity_type.endswith("s") else entity_type
            counts[key] = count
        
        return counts


# Singleton instance
_checkpoint_service: Optional[CheckpointService] = None


def get_checkpoint_service() -> CheckpointService:
    """Get or create checkpoint service instance."""
    global _checkpoint_service
    if _checkpoint_service is None:
        _checkpoint_service = CheckpointService()
    return _checkpoint_service
