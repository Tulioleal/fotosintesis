"""Migration 0012: durable enrichment telemetry observations.

Verifies the immutable observation table is created by the real migration
with closed-label, bounded-count, finite-duration constraints, an insert
trigger that enforces job correctness, an immutability trigger that rejects
UPDATE and DELETE, and a deferred constraint trigger that requires exactly one
matching observation for every new terminal enrichment transition. Historical
terminal jobs are neither backfilled nor rejected.
"""

from __future__ import annotations

import asyncio
import math
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from .conftest import BASE_DATABASE_URL

BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def _run_alembic(database_url: str, revision: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _run_alembic_downgrade(database_url: str, revision: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "downgrade", revision],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _create_job(database_engine, *, job_type: str, status: str) -> str:
    job_id = str(uuid4())
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
                INSERT INTO application_jobs (
                    id, job_type, payload_version, payload, status,
                    idempotency_key, attempt_count, max_attempts
                ) VALUES (
                    CAST(:id AS uuid), :job_type, 1,
                    CAST('{"run_id": "' || CAST(:id AS text) || '"}' AS json),
                    :status, 'migration-telemetry-job-' || :id, 1, 3
                )
            """),
            {"id": job_id, "job_type": job_type, "status": status},
        )
    return job_id


async def _insert_observation(database_engine, *, job_id: str, row: dict) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
                INSERT INTO enrichment_telemetry_observations (
                    job_id, policy_label, lifecycle_outcome,
                    acquisition_avoided, local_covered_count,
                    final_covered_count, coverage_gain,
                    accepted_aspect_count, search_count,
                    duration_seconds
                ) VALUES (
                    CAST(:job_id AS uuid), :policy_label,
                    :lifecycle_outcome, :acquisition_avoided,
                    :local_covered_count, :final_covered_count,
                    :coverage_gain, :accepted_aspect_count,
                    :search_count, :duration_seconds
                )
            """),
            {**row, "job_id": job_id},
        )


async def _transition_job(
    database_engine, *, job_id: str, status: str
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
                UPDATE application_jobs
                SET status = :status, completed_at = NOW()
                WHERE id = CAST(:job_id AS uuid)
            """),
            {"job_id": job_id, "status": status},
        )


async def _transition_with_observation(
    database_engine, *, job_id: str, status: str, row: dict
) -> None:
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
                UPDATE application_jobs
                SET status = :status, completed_at = NOW()
                WHERE id = CAST(:job_id AS uuid)
            """),
            {"job_id": job_id, "status": status},
        )
        await connection.execute(
            text("""
                INSERT INTO enrichment_telemetry_observations (
                    job_id, policy_label, lifecycle_outcome,
                    acquisition_avoided, local_covered_count,
                    final_covered_count, coverage_gain,
                    accepted_aspect_count, search_count,
                    duration_seconds
                ) VALUES (
                    CAST(:job_id AS uuid), :policy_label,
                    :lifecycle_outcome, :acquisition_avoided,
                    :local_covered_count, :final_covered_count,
                    :coverage_gain, :accepted_aspect_count,
                    :search_count, :duration_seconds
                )
            """),
            {**row, "job_id": job_id},
        )


async def _observation_count(database_engine, *, job_id: str) -> int:
    async with database_engine.connect() as connection:
        return int(
            await connection.scalar(
                text("""
                    SELECT COUNT(*)
                    FROM enrichment_telemetry_observations
                    WHERE job_id = CAST(:job_id AS uuid)
                """),
                {"job_id": job_id},
            )
            or 0
        )


def _observation(*, outcome: str = "complete") -> dict:
    return {
        "policy_label": "1",
        "lifecycle_outcome": outcome,
        "acquisition_avoided": True,
        "local_covered_count": 5,
        "final_covered_count": 17,
        "coverage_gain": 12,
        "accepted_aspect_count": 12,
        "search_count": 3,
        "duration_seconds": 2.5,
    }


async def test_upgrade_0011_to_0012_creates_observation_table_with_closed_constraints() -> None:
    database_name = f"migration_{uuid4().hex}"
    admin_engine = create_async_engine(
        BASE_DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=False,
    )
    database_url = make_url(BASE_DATABASE_URL).set(database=database_name).render_as_string(
        hide_password=False
    )
    database_engine = None

    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        await _run_alembic(database_url, "0011_enrichment_hardening")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        # Historical terminal jobs exist before migration 0012 is applied.
        # The deferred trigger does not exist yet, so these commits succeed.
        historical_complete = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="complete"
        )
        historical_failed = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="failed"
        )
        await _create_job(
            database_engine, job_type="ingest_validated_claims", status="complete"
        )

        await _run_alembic(database_url, "0012_durable_enrichment")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        async with database_engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            constraint_names = set(
                (
                    await connection.execute(
                        text("""
                            SELECT constraint_name
                            FROM information_schema.table_constraints
                            WHERE table_schema = current_schema()
                              AND table_name = 'enrichment_telemetry_observations'
                        """)
                    )
                ).scalars()
            )
            observation_trigger_names = set(
                (
                    await connection.execute(
                        text("""
                            SELECT tgname
                            FROM pg_trigger
                            WHERE tgrelid = 'enrichment_telemetry_observations'::regclass
                              AND NOT tgisinternal
                        """)
                    )
                ).scalars()
            )
            terminal_trigger_names = set(
                (
                    await connection.execute(
                        text("""
                            SELECT tgname
                            FROM pg_trigger
                            WHERE tgrelid = 'application_jobs'::regclass
                              AND NOT tgisinternal
                              AND tgname = 'application_jobs_terminal_enrichment_observation'
                        """)
                    )
                ).scalars()
            )

        assert revision == "0012_durable_enrichment"
        assert {
            "ck_enrichment_telemetry_policy_label",
            "ck_enrichment_telemetry_lifecycle_outcome",
            "ck_enrichment_telemetry_local_covered_count",
            "ck_enrichment_telemetry_final_covered_count",
            "ck_enrichment_telemetry_coverage_gain",
            "ck_enrichment_telemetry_accepted_aspect_count",
            "ck_enrichment_telemetry_search_count",
            "ck_enrichment_telemetry_duration_seconds",
        } <= constraint_names
        assert {
            "enrichment_telemetry_observations_immutable",
            "enrichment_telemetry_observations_insert_guard",
        } <= observation_trigger_names
        assert terminal_trigger_names == {
            "application_jobs_terminal_enrichment_observation"
        }

        # Migration succeeds without historical backfill: historical terminal
        # jobs have no observations and were not rejected.
        assert (
            await _observation_count(
                database_engine, job_id=historical_complete
            )
            == 0
        )
        assert (
            await _observation_count(database_engine, job_id=historical_failed) == 0
        )

        # Every new terminal transition requires exactly one matching
        # observation in the same transaction.
        for outcome in ("complete", "partial", "failed"):
            job_id = await _create_job(
                database_engine, job_type="enrich_confirmed_plant", status="processing"
            )
            await _transition_with_observation(
                database_engine,
                job_id=job_id,
                status=outcome,
                row=_observation(outcome=outcome),
            )
            assert (
                await _observation_count(database_engine, job_id=job_id) == 1
            )

        valid_row = _observation()

        # A terminal transition without an observation cannot commit.
        no_observation_job = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="processing"
        )
        with pytest.raises(IntegrityError, match="exactly one"):
            await _transition_job(
                database_engine, job_id=no_observation_job, status="complete"
            )

        # A terminal transition followed by a mismatched observation rolls
        # back entirely: the job stays processing and has no observation.
        mismatch_job = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="processing"
        )
        with pytest.raises(IntegrityError, match="must match"):
            await _transition_with_observation(
                database_engine,
                job_id=mismatch_job,
                status="complete",
                row=_observation(outcome="partial"),
            )
        async with database_engine.connect() as connection:
            remaining_status = await connection.scalar(
                text("""
                    SELECT status FROM application_jobs
                    WHERE id = CAST(:job_id AS uuid)
                """),
                {"job_id": mismatch_job},
            )
        assert remaining_status == "processing"
        assert await _observation_count(database_engine, job_id=mismatch_job) == 0

        # Non-enrichment terminal jobs remain allowed without observations.
        await _create_job(
            database_engine, job_type="ingest_validated_claims", status="complete"
        )

        # Check-constraint cases: the observation outcome stays valid and the
        # job status matches it, so the insert trigger passes and the bounded
        # count/duration check constraints fire.
        constraint_cases = [
            {**valid_row, "policy_label": "2"},
            {**valid_row, "policy_label": "999"},
            {**valid_row, "policy_label": "https://example.org/policy/2"},
            {**valid_row, "policy_label": "free text"},
            {**valid_row, "local_covered_count": -1},
            {**valid_row, "local_covered_count": 101},
            {**valid_row, "final_covered_count": -1},
            {**valid_row, "final_covered_count": 101},
            {**valid_row, "coverage_gain": 101},
            {**valid_row, "coverage_gain": -101},
            {**valid_row, "accepted_aspect_count": -1},
            {**valid_row, "accepted_aspect_count": 101},
            {**valid_row, "search_count": -1},
            {**valid_row, "search_count": 101},
            {**valid_row, "duration_seconds": -0.5},
            {**valid_row, "duration_seconds": float("nan")},
            {**valid_row, "duration_seconds": float("inf")},
            {**valid_row, "duration_seconds": float("-inf")},
        ]
        for row in constraint_cases:
            job_id = await _create_job(
                database_engine, job_type="enrich_confirmed_plant", status="processing"
            )
            with pytest.raises(IntegrityError, match="ck_enrichment_telemetry"):
                await _transition_with_observation(
                    database_engine,
                    job_id=job_id,
                    status="complete",
                    row=row,
                )

        # The lifecycle outcome must be closed; the insert trigger rejects an
        # outcome that cannot match a terminal job status.
        for invalid_outcome in ("lease_lost", "arbitrary"):
            job_id = await _create_job(
                database_engine, job_type="enrich_confirmed_plant", status="processing"
            )
            with pytest.raises(IntegrityError, match="must match"):
                await _transition_with_observation(
                    database_engine,
                    job_id=job_id,
                    status="complete",
                    row={**valid_row, "lifecycle_outcome": invalid_outcome},
                )

        # A non-enrichment job cannot be recorded as an enrichment observation.
        ingest_job = await _create_job(
            database_engine, job_type="ingest_validated_claims", status="processing"
        )
        with pytest.raises(IntegrityError, match="enrich_confirmed_plant"):
            await _insert_observation(
                database_engine, job_id=ingest_job, row=_observation(outcome="complete")
            )

        # A non-terminal job cannot be recorded.
        pending_job = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="processing"
        )
        with pytest.raises(IntegrityError, match="terminal job"):
            await _insert_observation(
                database_engine, job_id=pending_job, row=_observation(outcome="failed")
            )

        # The primary key is the job id: a duplicate job insert is rejected.
        duplicate_job = await _create_job(
            database_engine, job_type="enrich_confirmed_plant", status="processing"
        )
        await _transition_with_observation(
            database_engine,
            job_id=duplicate_job,
            status="complete",
            row=_observation(outcome="complete"),
        )
        with pytest.raises(IntegrityError, match="enrichment_telemetry_observations_pkey"):
            await _insert_observation(
                database_engine, job_id=duplicate_job, row=_observation(outcome="complete")
            )

        # Observations are immutable: UPDATE and DELETE are rejected.
        with pytest.raises(IntegrityError, match="immutable"):
            async with database_engine.begin() as connection:
                await connection.execute(
                    text("""
                        UPDATE enrichment_telemetry_observations
                        SET coverage_gain = 50
                        WHERE job_id = CAST(:job_id AS uuid)
                    """),
                    {"job_id": duplicate_job},
                )
        with pytest.raises(IntegrityError, match="immutable"):
            async with database_engine.begin() as connection:
                await connection.execute(
                    text("""
                        DELETE FROM enrichment_telemetry_observations
                        WHERE job_id = CAST(:job_id AS uuid)
                    """),
                    {"job_id": duplicate_job},
                )

        async with database_engine.connect() as connection:
            stored = (
                await connection.execute(
                    text("""
                        SELECT job_id, policy_label, lifecycle_outcome,
                               acquisition_avoided, local_covered_count,
                               final_covered_count, coverage_gain,
                               accepted_aspect_count, search_count,
                               duration_seconds
                        FROM enrichment_telemetry_observations
                        WHERE lifecycle_outcome = 'complete'
                        ORDER BY created_at ASC
                        LIMIT 1
                    """)
                )
            ).mappings().one()
        assert stored["policy_label"] == "1"
        assert stored["lifecycle_outcome"] == "complete"
        assert stored["acquisition_avoided"] is True
        assert stored["coverage_gain"] == 12
        assert stored["duration_seconds"] == 2.5

        # Downgrade removes the table, its triggers/functions, and the
        # deferred constraint trigger and function.
        await _run_alembic_downgrade(database_url, "0011_enrichment_hardening")
        async with database_engine.connect() as connection:
            exists = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = 'enrichment_telemetry_observations'
                """)
            )
            orphan_trigger = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM pg_trigger
                    WHERE tgname = 'application_jobs_terminal_enrichment_observation'
                      AND NOT tgisinternal
                """)
            )
            orphan_function = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM pg_proc
                    WHERE proname = 'require_terminal_enrichment_observation'
                """)
            )
        assert exists == 0
        assert orphan_trigger == 0
        assert orphan_function == 0
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
                )
        finally:
            await admin_engine.dispose()
