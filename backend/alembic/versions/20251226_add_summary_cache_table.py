"""add_summary_cache_table

Revision ID: 20251226_summary_cache
Revises: 20251225_merge_log
Create Date: 2025-12-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251226_summary_cache'
down_revision: Union[str, None] = '20251225_merge_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create summary_cache table
    op.create_table(
        'summary_cache',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('analysis_id', sa.UUID(), nullable=False),
        sa.Column('config_hash', sa.String(length=64), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key')
    )
    op.create_index('ix_summary_cache_cache_key', 'summary_cache', ['cache_key'], unique=True)
    op.create_index('ix_summary_cache_entity_id', 'summary_cache', ['entity_id'], unique=False)
    op.create_index('ix_summary_cache_analysis_id', 'summary_cache', ['analysis_id'], unique=False)
    op.create_index('ix_summary_cache_config_hash', 'summary_cache', ['config_hash'], unique=False)
    op.create_index('ix_summary_cache_entity_config', 'summary_cache', ['entity_id', 'config_hash'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_summary_cache_entity_config', table_name='summary_cache')
    op.drop_index('ix_summary_cache_config_hash', table_name='summary_cache')
    op.drop_index('ix_summary_cache_analysis_id', table_name='summary_cache')
    op.drop_index('ix_summary_cache_entity_id', table_name='summary_cache')
    op.drop_index('ix_summary_cache_cache_key', table_name='summary_cache')

    # Drop table
    op.drop_table('summary_cache')
