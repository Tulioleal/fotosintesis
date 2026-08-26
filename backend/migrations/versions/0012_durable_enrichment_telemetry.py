"""durable enrichment telemetry: immutable terminal observations

Revision ID: 0012_durable_enrichment
Revises: 0011_enrichment_hardening
Create Date: 2026-08-11

Each terminal enrichment job produces exactly one immutable observation row,
inserted atomically with the terminal job transition. Rows are observations,
not consumable messages: no delivered_at column, no claims, species, URLs,
job payloads, idempotency keys, or errors. No historical backfill.

Immutable PostgreSQL observation is a database invariant: an UPDATE or
DELETE trigger rejects any mutation after insertion. An insert trigger
verifies that the referenced job exists, is the enrichment job type, is
terminal, and that its status matches the recorded lifecycle outcome.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_durable_enrichment"
down_revision: Union[str, None] = "0011_enrichment_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enrichment_telemetry_observations",
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("policy_label", sa.String(length=40), nullable=False),
        sa.Column("lifecycle_outcome", sa.String(length=20), nullable=False),
        sa.Column("acquisition_avoided", sa.Boolean(), nullable=False),
        sa.Column("local_covered_count", sa.Integer(), nullable=False),
        sa.Column("final_covered_count", sa.Integer(), nullable=False),
        sa.Column("coverage_gain", sa.Integer(), nullable=False),
        sa.Column("accepted_aspect_count", sa.Integer(), nullable=False),
        sa.Column("search_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "policy_label IN ('1', 'unsupported')",
            name="ck_enrichment_telemetry_policy_label",
        ),
        sa.CheckConstraint(
            "lifecycle_outcome IN ('complete', 'partial', 'failed')",
            name="ck_enrichment_telemetry_lifecycle_outcome",
        ),
        sa.CheckConstraint(
            "local_covered_count >= 0 AND local_covered_count <= 100",
            name="ck_enrichment_telemetry_local_covered_count",
        ),
        sa.CheckConstraint(
            "final_covered_count >= 0 AND final_covered_count <= 100",
            name="ck_enrichment_telemetry_final_covered_count",
        ),
        sa.CheckConstraint(
            "coverage_gain >= -100 AND coverage_gain <= 100",
            name="ck_enrichment_telemetry_coverage_gain",
        ),
        sa.CheckConstraint(
            "accepted_aspect_count >= 0 AND accepted_aspect_count <= 100",
            name="ck_enrichment_telemetry_accepted_aspect_count",
        ),
        sa.CheckConstraint(
            "search_count >= 0 AND search_count <= 100",
            name="ck_enrichment_telemetry_search_count",
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0 AND duration_seconds < 'Infinity'::float8",
            name="ck_enrichment_telemetry_duration_seconds",
        ),
    )

    op.execute(
        """
        CREATE FUNCTION enforce_enrichment_telemetry_immutability()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'enrichment telemetry observations are immutable'
              USING ERRCODE = 'check_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER enrichment_telemetry_observations_immutable
        BEFORE UPDATE OR DELETE ON enrichment_telemetry_observations
        FOR EACH ROW EXECUTE FUNCTION enforce_enrichment_telemetry_immutability()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_enrichment_telemetry_observation_job()
        RETURNS trigger AS $$
        DECLARE
            job_status_value TEXT;
        BEGIN
            SELECT status INTO job_status_value
            FROM application_jobs
            WHERE id = NEW.job_id;

            IF job_status_value IS NULL THEN
                RAISE EXCEPTION 'enrichment telemetry observation references an unknown job'
                  USING ERRCODE = 'foreign_key_violation';
            END IF;

            IF (SELECT job_type FROM application_jobs WHERE id = NEW.job_id)
                <> 'enrich_confirmed_plant' THEN
                RAISE EXCEPTION 'enrichment telemetry observation requires enrich_confirmed_plant job'
                  USING ERRCODE = 'check_violation';
            END IF;

            IF job_status_value NOT IN ('complete', 'partial', 'failed') THEN
                RAISE EXCEPTION 'enrichment telemetry observation requires a terminal job'
                  USING ERRCODE = 'check_violation';
            END IF;

            IF NEW.lifecycle_outcome <> job_status_value THEN
                RAISE EXCEPTION 'enrichment telemetry outcome must match the terminal job status'
                  USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER enrichment_telemetry_observations_insert_guard
        BEFORE INSERT ON enrichment_telemetry_observations
        FOR EACH ROW EXECUTE FUNCTION validate_enrichment_telemetry_observation_job()
        """
    )

    op.execute(
        """
        CREATE FUNCTION require_terminal_enrichment_observation()
        RETURNS trigger AS $$
        DECLARE
            observation_count INTEGER;
        BEGIN
            IF NEW.job_type <> 'enrich_confirmed_plant'
               OR NEW.status NOT IN ('complete', 'partial', 'failed') THEN
                RETURN NEW;
            END IF;

            SELECT COUNT(*) INTO observation_count
            FROM enrichment_telemetry_observations
            WHERE job_id = NEW.id
              AND lifecycle_outcome = NEW.status;

            IF observation_count <> 1 THEN
                RAISE EXCEPTION
                  'terminal enrichment job requires exactly one matching observation'
                  USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    # Deferred because the worker updates the job to its terminal status and
    # inserts the observation in the same transaction; the check runs at
    # commit, after both writes. The trigger only governs transitions after
    # installation, so historical terminal jobs are neither scanned nor
    # rejected and no backfill is performed.
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER application_jobs_terminal_enrichment_observation
        AFTER INSERT OR UPDATE ON application_jobs
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION require_terminal_enrichment_observation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS application_jobs_terminal_enrichment_observation "
        "ON application_jobs"
    )
    op.execute("DROP FUNCTION IF EXISTS require_terminal_enrichment_observation()")
    op.execute(
        "DROP TRIGGER IF EXISTS enrichment_telemetry_observations_insert_guard "
        "ON enrichment_telemetry_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_enrichment_telemetry_observation_job()")
    op.execute(
        "DROP TRIGGER IF EXISTS enrichment_telemetry_observations_immutable "
        "ON enrichment_telemetry_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_enrichment_telemetry_immutability()")
    op.drop_table("enrichment_telemetry_observations")
