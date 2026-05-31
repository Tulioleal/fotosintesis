"""plant identification taxonomy

Revision ID: 0003_plant_id_taxonomy
Revises: 0002_authentication_home
Create Date: 2026-05-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_plant_id_taxonomy"
down_revision: Union[str, None] = "0002_authentication_home"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identification_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("sad_path", sa.String(length=80), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "identification_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "identification_id",
            sa.Uuid(),
            sa.ForeignKey("identification_images.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("common_name", sa.String(length=180), nullable=True),
        sa.Column("suggested_scientific_name", sa.String(length=240), nullable=False),
        sa.Column("confidence_label", sa.String(length=40), nullable=False),
        sa.Column("visible_traits", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("possible_match_copy", sa.Text(), nullable=False),
        sa.Column("gbif_key", sa.Integer(), nullable=True),
        sa.Column("gbif_accepted_key", sa.Integer(), nullable=True),
        sa.Column("accepted_scientific_name", sa.String(length=240), nullable=True),
        sa.Column("taxonomic_status", sa.String(length=80), nullable=True),
        sa.Column("synonyms", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("genus", sa.String(length=160), nullable=True),
        sa.Column("family", sa.String(length=160), nullable=True),
        sa.Column("species", sa.String(length=240), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("identification_candidates")
    op.drop_table("identification_images")
