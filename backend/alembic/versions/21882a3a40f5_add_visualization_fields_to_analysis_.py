"""Add visualization fields to analysis_jobs

Revision ID: 21882a3a40f5
Revises: eddc1b69c903
Create Date: 2025-12-24 10:54:29.148945

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21882a3a40f5'
down_revision: Union[str, None] = 'eddc1b69c903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add visualization fields to analysis_jobs table
    op.add_column('analysis_jobs', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('analysis_jobs', sa.Column('projected_gdp', sa.ARRAY(sa.Integer()), nullable=True))
    op.add_column('analysis_jobs', sa.Column('social_stability', sa.ARRAY(sa.Integer()), nullable=True))
    op.add_column('analysis_jobs', sa.Column('timeline_labels', sa.ARRAY(sa.String(50)), nullable=True))


def downgrade() -> None:
    # Remove visualization fields from analysis_jobs table
    op.drop_column('analysis_jobs', 'timeline_labels')
    op.drop_column('analysis_jobs', 'social_stability')
    op.drop_column('analysis_jobs', 'projected_gdp')
    op.drop_column('analysis_jobs', 'summary')
