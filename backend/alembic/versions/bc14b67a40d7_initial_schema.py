"""initial_schema

Revision ID: bc14b67a40d7
Revises: 
Create Date: 2024-12-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bc14b67a40d7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. analysis_jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('scope', postgresql.JSONB(), server_default='{}'),
        sa.Column('depth', sa.String(20), server_default='standard'),
        sa.Column('status', sa.String(20), server_default='created'),
        sa.Column('current_stage', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('entities_count', postgresql.JSONB(), server_default='{"actors":0,"policies":0,"outcomes":0,"risks":0}'),
        sa.Column('tokens_used', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_analysis_jobs_status', 'analysis_jobs', ['status'])

    # 2. documents
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('content_type', sa.String(50), server_default='text/plain'),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('doc_metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_documents_analysis_id', 'documents', ['analysis_id'])

    # 3. chunks
    op.create_table(
        'chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), server_default='0'),
        sa.Column('extraction_status', sa.String(20), server_default='pending'),
        sa.Column('extraction_result', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'])
    op.create_index('ix_chunks_analysis_id', 'chunks', ['analysis_id'])
    op.create_index('ix_chunks_extraction_status', 'chunks', ['extraction_status'])

    # 4. entities
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('label', sa.String(500), nullable=False),
        sa.Column('aliases', postgresql.ARRAY(sa.Text()), server_default='{}'),
        sa.Column('confidence', sa.Integer(), server_default='50'),
        sa.Column('impact_score', sa.Integer(), server_default='50'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), server_default='false'),
        sa.Column('merged_into', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint("entity_type IN ('actor', 'policy', 'outcome', 'risk')", name='check_entity_type'),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 100", name='check_confidence_range'),
    )
    op.create_index('ix_entities_analysis_id', 'entities', ['analysis_id'])
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'])
    op.create_index('ix_entities_is_resolved', 'entities', ['is_resolved'])

    # 5. entity_provenance
    op.create_table(
        'entity_provenance',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chunks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Integer(), server_default='50'),
    )
    op.create_index('ix_entity_provenance_entity_id', 'entity_provenance', ['entity_id'])
    op.create_index('ix_entity_provenance_chunk_id', 'entity_provenance', ['chunk_id'])

    # 6. relationships
    op.create_table(
        'relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Integer(), server_default='50'),
        sa.UniqueConstraint('analysis_id', 'source_entity_id', 'target_entity_id', 'relationship_type', name='unique_relationship'),
    )
    op.create_index('ix_relationships_analysis_id', 'relationships', ['analysis_id'])
    op.create_index('ix_relationships_source_entity_id', 'relationships', ['source_entity_id'])
    op.create_index('ix_relationships_target_entity_id', 'relationships', ['target_entity_id'])

    # 7. checkpoints
    op.create_table(
        'checkpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('stats', postgresql.JSONB(), server_default='{}'),
        sa.Column('graph_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_checkpoints_analysis_id', 'checkpoints', ['analysis_id'])

    # 8. progress_events
    op.create_table(
        'progress_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('data', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_progress_events_analysis_id', 'progress_events', ['analysis_id'])
    op.create_index('ix_progress_events_created_at', 'progress_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('progress_events')
    op.drop_table('checkpoints')
    op.drop_table('relationships')
    op.drop_table('entity_provenance')
    op.drop_table('entities')
    op.drop_table('chunks')
    op.drop_table('documents')
    op.drop_table('analysis_jobs')
