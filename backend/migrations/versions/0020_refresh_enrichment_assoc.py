"""durable refresh-enrichment causal association

Revision ID: 0020_refresh_enrichment_assoc
Revises: 0019_manual_plant_search
Create Date: 2026-08-22

Adds the many-to-many association between profile-refresh jobs and the
enrichment jobs that caused them. One enrichment run may trigger one refresh
and a reused refresh job may serve several enrichment runs, so the link is
durable and idempotent rather than inferred from payload species matching.

Historical refresh jobs without an association stay unexposed in activity
views; no backfill is required.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_refresh_enrichment_assoc"
down_revision: Union[str, None] = "0019_manual_plant_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_refresh_enrichment_jobs",
        sa.Column(
            "refresh_job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enrichment_job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "refresh_job_id",
            "enrichment_job_id",
            name="pk_profile_refresh_enrichment_jobs",
        ),
    )
    op.create_index(
        "ix_profile_refresh_enrichment_jobs_enrichment_id",
        "profile_refresh_enrichment_jobs",
        ["enrichment_job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profile_refresh_enrichment_jobs_enrichment_id",
        table_name="profile_refresh_enrichment_jobs",
    )
    op.drop_table("profile_refresh_enrichment_jobs")
