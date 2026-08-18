import sqlalchemy as sa

from app.auth.tables import metadata as auth_metadata
from app.limiter.policy import Dimension, EndpointCategory

# The limiter table lives in the shared auth metadata so repository tests,
# the Alembic environment, and the SQLite test fixture all see it without
# separate wiring.
metadata = auth_metadata

limiter_state = sa.Table(
    "auth_limiter_state",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("dimension", sa.String(length=16), nullable=False),
    sa.Column("category", sa.String(length=48), nullable=False),
    sa.Column("digest_key", sa.String(length=64), nullable=False),
    sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint(
        "dimension",
        "category",
        "digest_key",
        "window_start",
        name="uq_auth_limiter_state_dimension_category_key_window",
    ),
    sa.CheckConstraint(
        f"dimension IN ({', '.join(repr(d.value) for d in Dimension)})",
        name="ck_auth_limiter_state_dimension",
    ),
    sa.CheckConstraint(
        f"category IN ({', '.join(repr(c.value) for c in EndpointCategory)})",
        name="ck_auth_limiter_state_category",
    ),
    sa.CheckConstraint("count >= 0", name="ck_auth_limiter_state_count"),
    sa.CheckConstraint("window_end > window_start", name="ck_auth_limiter_state_window"),
)
sa.Index(
    "ix_auth_limiter_state_window_end",
    limiter_state.c.window_end,
)
