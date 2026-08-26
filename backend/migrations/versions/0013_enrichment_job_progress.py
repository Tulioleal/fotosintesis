"""durable enrichment progress checkpoints

Revision ID: 0013_enrichment_job_progress
Revises: 0012_durable_enrichment
Create Date: 2026-08-13

Each enrichment job carries one durable progress row that records immutable
policy/aspect identity and only-growing persisted and indexed coverage. The
worker finalizes partial or failed outcomes from this checkpoint, never from
a handler's zero snapshot, so useful accepted evidence can never be reported
as total failure. No historical backfill is performed and migration 0012
telemetry is untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_enrichment_job_progress"
down_revision: Union[str, None] = "0012_durable_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enrichment_job_progress",
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("required_aspects", sa.JSON(), nullable=False),
        sa.Column("local_covered_aspects", sa.JSON(), nullable=False),
        sa.Column("persisted_covered_aspects", sa.JSON(), nullable=False),
        sa.Column("indexed_covered_aspects", sa.JSON(), nullable=False),
        sa.Column("final_judged_covered_aspects", sa.JSON(), nullable=True),
        sa.Column("final_judged_missing_aspects", sa.JSON(), nullable=True),
        sa.Column("answerability_status", sa.String(length=20), nullable=True),
        sa.Column(
            "acquisition_avoided",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("search_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "accepted_aspect_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_validation_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "policy_version >= 1",
            name="ck_enrichment_job_progress_policy_version",
        ),
        sa.CheckConstraint(
            "answerability_status IS NULL OR answerability_status IN "
            "('full', 'partial', 'insufficient', 'contradictory')",
            name="ck_enrichment_job_progress_answerability_status",
        ),
        sa.CheckConstraint(
            "search_count >= 0 AND search_count <= 100",
            name="ck_enrichment_job_progress_search_count",
        ),
        sa.CheckConstraint(
            "accepted_aspect_count >= 0 AND accepted_aspect_count <= 100",
            name="ck_enrichment_job_progress_accepted_aspect_count",
        ),
    )


def downgrade() -> None:
    op.drop_table("enrichment_job_progress")
