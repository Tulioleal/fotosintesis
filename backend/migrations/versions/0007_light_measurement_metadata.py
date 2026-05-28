"""light measurement metadata

Revision ID: 0007_light_measurement_metadata
Revises: 0006_assistant_agent
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_light_measurement_metadata"
down_revision: Union[str, None] = "0006_assistant_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "light_measurements",
        sa.Column("source", sa.String(length=40), nullable=False, server_default="sensor"),
    )
    op.add_column(
        "light_measurements",
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("light_measurements", "metadata")
    op.drop_column("light_measurements", "source")
