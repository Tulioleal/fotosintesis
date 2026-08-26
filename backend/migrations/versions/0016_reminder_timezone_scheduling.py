"""reminder timezone scheduling integrity

Revision ID: 0016_reminder_timezone
Revises: 0015_auth_limiter_state
Create Date: 2026-08-18

Adds nullable IANA timezone columns to the users and reminders tables so that
reminder scheduling can resolve local wall-clock values to a correct UTC
instant and preserve recurrence across DST. Existing rows stay null, which
marks legacy UTC interpretation; no existing instants are shifted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_reminder_timezone"
down_revision: Union[str, None] = "0015_auth_limiter_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(length=80), nullable=True))
    op.add_column("reminders", sa.Column("timezone", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("reminders", "timezone")
    op.drop_column("users", "timezone")
