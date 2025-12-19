"""fix_critical_schema_issues

Revision ID: b20cdd07059f
Revises: aa6599cfaa16
Create Date: 2025-12-18 13:27:21.542315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b20cdd07059f'
down_revision: Union[str, None] = 'aa6599cfaa16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add UUID defaults to all tables missing them
    op.execute(sa.text("ALTER TABLE sources ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE documents ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE chunks ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE entities ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE entity_provenance ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE relationships ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE checkpoints ALTER COLUMN id SET DEFAULT gen_random_uuid()"))
    op.execute(sa.text("ALTER TABLE query_expansions ALTER COLUMN id SET DEFAULT gen_random_uuid()"))

    # 2. Create trigger function for updated_at column
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """))

    # Create trigger on analysis_jobs table
    op.execute(sa.text("""
        CREATE TRIGGER update_analysis_jobs_updated_at
            BEFORE UPDATE ON analysis_jobs
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """))

    # 3. Fix documents.source_id foreign key to use ON DELETE SET NULL
    op.drop_constraint('documents_source_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_source_id_fkey',
        'documents', 'sources',
        ['source_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add missing index on documents.source_id
    op.create_index('ix_documents_source_id', 'documents', ['source_id'], unique=False)

    # 4. Add composite indexes for common query patterns
    # For dashboard queries filtering by analysis and status
    op.create_index(
        'ix_analysis_jobs_analysis_status',
        'analysis_jobs',
        ['id', 'status'],
        unique=False
    )

    # For filtering entities by analysis and type
    op.create_index(
        'ix_entities_analysis_type',
        'entities',
        ['analysis_id', 'entity_type'],
        unique=False
    )

    # For retrieving chunks in order by document
    op.create_index(
        'ix_chunks_document_sequence',
        'chunks',
        ['document_id', 'sequence'],
        unique=False
    )

    # For real-time event streaming (DESC for latest first)
    op.execute(sa.text("""
        CREATE INDEX ix_progress_events_analysis_created
        ON progress_events (analysis_id, created_at DESC)
    """))

    # 5. Add CHECK constraint for impact_score
    op.create_check_constraint(
        'check_impact_score_range',
        'entities',
        'impact_score >= 0 AND impact_score <= 100'
    )


def downgrade() -> None:
    # Remove CHECK constraint
    op.drop_constraint('check_impact_score_range', 'entities', type_='check')

    # Remove composite indexes
    op.drop_index('ix_progress_events_analysis_created', table_name='progress_events')
    op.drop_index('ix_chunks_document_sequence', table_name='chunks')
    op.drop_index('ix_entities_analysis_type', table_name='entities')
    op.drop_index('ix_analysis_jobs_analysis_status', table_name='analysis_jobs')

    # Remove documents.source_id index
    op.drop_index('ix_documents_source_id', table_name='documents')

    # Revert documents.source_id foreign key back to no action
    op.drop_constraint('documents_source_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_source_id_fkey',
        'documents', 'sources',
        ['source_id'], ['id']
    )

    # Remove trigger and function
    op.execute(sa.text("DROP TRIGGER IF EXISTS update_analysis_jobs_updated_at ON analysis_jobs"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at_column()"))

    # Remove UUID defaults
    op.execute(sa.text("ALTER TABLE sources ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE documents ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE chunks ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE entities ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE entity_provenance ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE relationships ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE checkpoints ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE query_expansions ALTER COLUMN id DROP DEFAULT"))
