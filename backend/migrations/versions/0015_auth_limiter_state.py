"""auth limiter state

Revision ID: 0015_auth_limiter_state
Revises: 0014_profile_canonical_identity
Create Date: 2026-08-14

Adds the shared persistent limiter table that backs distributed
authentication abuse limits. Rows hold only opaque keyed digests plus the
dimension, closed endpoint category, bounded count, and window timestamps
required for enforcement; no raw account or source identifiers are stored.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_auth_limiter_state"
down_revision: Union[str, None] = "0014_profile_canonical_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_limiter_state",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dimension", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("digest_key", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dimension",
            "category",
            "digest_key",
            "window_start",
            name="uq_auth_limiter_state_dimension_category_key_window",
        ),
        sa.CheckConstraint(
            "dimension IN ('source', 'account')",
            name="ck_auth_limiter_state_dimension",
        ),
        sa.CheckConstraint(
            "category IN ('registration', 'credential_verification', "
            "'recovery_initiation', 'recovery_confirmation', 'authjs_post')",
            name="ck_auth_limiter_state_category",
        ),
        sa.CheckConstraint("count >= 0", name="ck_auth_limiter_state_count"),
        sa.CheckConstraint(
            "window_end > window_start",
            name="ck_auth_limiter_state_window",
        ),
    )
    op.create_index(
        "ix_auth_limiter_state_window_end",
        "auth_limiter_state",
        ["window_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_limiter_state_window_end", table_name="auth_limiter_state")
    op.drop_table("auth_limiter_state")
