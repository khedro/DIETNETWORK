"""job sample_count

Revision ID: 5c1d2e7a9b40
Revises: 38afb3b0bf90
Create Date: 2026-10-13 00:00:00.000000

Number of samples in a job's upload, kept for usage statistics (see
ops/usage_stats.sql). Unlike `predictions` it survives the 30-day retention
purge, so totals stay complete over a whole grant-reporting period.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c1d2e7a9b40'
down_revision: Union[str, None] = '38afb3b0bf90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('sample_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'sample_count')
