"""recovery token hashing and one-time use

Revision ID: 0017_recovery_token_hashing
Revises: 0016_reminder_timezone
Create Date: 2026-08-18

Migrates password recovery tokens from cleartext ``token`` values to a
persisted one-way ``token_hash`` and adds ``used_at`` / ``invalidated_at``
use-state columns. Existing cleartext rows are invalidated rather than
converted so legacy tokens cannot be replayed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_recovery_token_hashing"
down_revision: Union[str, None] = "0016_reminder_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recovery_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "recovery_tokens",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recovery_tokens",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Invalidate all legacy cleartext rows so they can never be replayed. The
    # token_hash column is UNIQUE, so each invalidated row gets a distinct,
    # unusable placeholder derived from its id.
    op.execute(
        "UPDATE recovery_tokens SET invalidated_at = now(), token_hash = 'legacy:' || id::text WHERE invalidated_at IS NULL"
    )

    op.alter_column("recovery_tokens", "token_hash", nullable=False)
    op.create_index(
        "ix_recovery_tokens_token_hash", "recovery_tokens", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_recovery_tokens_user_active",
        "recovery_tokens",
        ["user_id"],
        postgresql_where=sa.text("used_at IS NULL AND invalidated_at IS NULL"),
    )
    op.drop_index("ix_recovery_tokens_token", table_name="recovery_tokens")
    op.drop_column("recovery_tokens", "token")


def downgrade() -> None:
    op.add_column(
        "recovery_tokens",
        sa.Column("token", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_recovery_tokens_token", "recovery_tokens", ["token"], unique=True)
    op.drop_index("ix_recovery_tokens_user_active", table_name="recovery_tokens")
    op.drop_index("ix_recovery_tokens_token_hash", table_name="recovery_tokens")
    op.drop_column("recovery_tokens", "invalidated_at")
    op.drop_column("recovery_tokens", "used_at")
    op.drop_column("recovery_tokens", "token_hash")
