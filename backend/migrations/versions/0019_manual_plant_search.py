"""manual plant search candidate origin and ownership

Revision ID: 0019_manual_plant_search
Revises: 0018_profile_section_versions
Create Date: 2026-08-19

Makes identification_candidates support manual search candidates that are not
tied to an identification image:

- identification_id becomes nullable (manual candidates have no image).
- origin records whether the candidate came from image_identification or
  manual_search, defaulting to image_identification for existing rows.
- user_id is a nullable FK set only for manual candidates; image candidates
  keep their ownership resolved through the image row.

Existing rows keep origin=image_identification and null user_id, so no backfill
is required.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0019_manual_plant_search"
down_revision: Union[str, None] = "0018_profile_section_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "identification_candidates",
        "identification_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column(
        "identification_candidates",
        sa.Column(
            "origin",
            sa.String(length=40),
            nullable=False,
            server_default="image_identification",
        ),
    )
    op.add_column(
        "identification_candidates",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "identification_candidates_user_id_fkey",
        "identification_candidates",
        type_="foreignkey",
    )
    op.drop_column("identification_candidates", "user_id")
    op.drop_column("identification_candidates", "origin")
    op.alter_column(
        "identification_candidates",
        "identification_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
