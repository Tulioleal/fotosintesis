"""authentication home

Revision ID: 0002_authentication_home
Revises: 0001_initial_foundation
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_authentication_home"
down_revision: Union[str, None] = "0001_initial_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True, index=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_account_id", sa.String(length=160), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("token_type", sa.String(length=80), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column("session_state", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_accounts_provider_account"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "verification_tokens",
        sa.Column("identifier", sa.String(length=320), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("identifier", "token"),
    )
    op.create_table(
        "recovery_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recovery_tokens")
    op.drop_table("verification_tokens")
    op.drop_table("sessions")
    op.drop_table("accounts")
    op.drop_table("users")
