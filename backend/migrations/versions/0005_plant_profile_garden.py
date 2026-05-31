"""plant profile garden

Revision ID: 0005_plant_profile_garden
Revises: 0004_knowledge_rag
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_plant_profile_garden"
down_revision: Union[str, None] = "0004_knowledge_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plant_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scientific_name", sa.String(length=240), nullable=False),
        sa.Column("common_name", sa.String(length=180), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("sections", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_plant_profiles_scientific_name",
        "plant_profiles",
        ["scientific_name"],
        unique=True,
    )

    op.create_table(
        "garden_plants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("plant_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "confirmed_candidate_id",
            sa.Uuid(),
            sa.ForeignKey("identification_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nickname", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=180), nullable=True),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("custom_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("active_reminders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_garden_plants_user_id", "garden_plants", ["user_id"])
    op.create_index("ix_garden_plants_profile_id", "garden_plants", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_garden_plants_profile_id", table_name="garden_plants")
    op.drop_index("ix_garden_plants_user_id", table_name="garden_plants")
    op.drop_table("garden_plants")
    op.drop_index("ix_plant_profiles_scientific_name", table_name="plant_profiles")
    op.drop_table("plant_profiles")
