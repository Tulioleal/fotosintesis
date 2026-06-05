"""identification candidate binomial name

Revision ID: 0008_candidate_binomial_name
Revises: 0007_light_metadata
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_candidate_binomial_name"
down_revision: Union[str, None] = "0007_light_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "identification_candidates",
        sa.Column("binomial_name", sa.String(length=240), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("identification_candidates", "binomial_name")
