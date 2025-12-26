"""add_entity_merge_log_and_indexes

Revision ID: 20251225_merge_log
Revises: 21882a3a40f5
Create Date: 2025-12-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251225_merge_log'
down_revision: Union[str, None] = '21882a3a40f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_merge_log table
    op.create_table(
        'entity_merge_log',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('analysis_id', sa.UUID(), nullable=False),
        sa.Column('primary_entity_id', sa.UUID(), nullable=True),
        sa.Column('merged_entity_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('merge_method', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('canonical_label', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entity_merge_log_analysis_id', 'entity_merge_log', ['analysis_id'], unique=False)

    # Add performance indexes for entities
    # Note: ix_entities_analysis_type already exists in database
    op.create_index('ix_entities_label_lower', 'entities', [sa.text('lower(label)')], unique=False)

    # Note: relationship indexes already exist from initial schema
    # Verified: ix_relationships_source_entity_id and ix_relationships_target_entity_id


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_entities_label_lower', table_name='entities')
    op.drop_index('ix_entity_merge_log_analysis_id', table_name='entity_merge_log')

    # Drop table
    op.drop_table('entity_merge_log')
