"""Check graph data in database"""
import asyncio
from sqlalchemy import select
from app.models.database import AnalysisJob, Entity, Relationship
from app.core.database_config import async_session_maker

async def check_data():
    async with async_session_maker() as db:
        # Get latest analysis
        result = await db.execute(
            select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(1)
        )
        analysis = result.scalar_one_or_none()

        if not analysis:
            print('No analyses found')
            return

        print(f'Latest analysis: {analysis.id}')
        print(f'Query: {analysis.query}')
        print(f'Status: {analysis.status}')
        print()

        # Count entities
        entity_result = await db.execute(
            select(Entity)
            .where(Entity.analysis_id == analysis.id)
            .where(Entity.merged_into == None)
        )
        entities = entity_result.scalars().all()
        print(f'Total entities (non-merged): {len(entities)}')

        for e in entities[:10]:
            print(f'  - [{e.entity_type}] {e.label} (confidence: {e.confidence}, impact: {e.impact_score})')

        if len(entities) > 10:
            print(f'  ... and {len(entities) - 10} more')

        print()

        # Count relationships
        rel_result = await db.execute(
            select(Relationship).where(Relationship.analysis_id == analysis.id)
        )
        relationships = rel_result.scalars().all()
        print(f'Total relationships: {len(relationships)}')

        for r in relationships[:10]:
            print(f'  - {r.source_entity_id} -> {r.target_entity_id}: {r.relationship_type} ({r.confidence})')

        if len(relationships) > 10:
            print(f'  ... and {len(relationships) - 10} more')

if __name__ == '__main__':
    asyncio.run(check_data())
