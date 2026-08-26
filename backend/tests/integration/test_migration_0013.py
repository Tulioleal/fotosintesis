"""Migration 0013: durable enrichment progress checkpoints.

Verifies the real migration creates ``enrichment_job_progress`` with an
immutable-policy design (bounded non-negative counts, closed answerability
set, FK to ``application_jobs.id``), leaves migration 0012 telemetry intact,
and downgrades cleanly. No historical backfill is performed.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert, text
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


async def _create_job(database_engine) -> str:
    job_id = str(uuid4())
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
                INSERT INTO application_jobs (
                    id, job_type, payload_version, payload, status,
                    idempotency_key, attempt_count, max_attempts
                ) VALUES (
                    CAST(:id AS uuid), 'enrich_confirmed_plant', 1,
                    CAST('{"run_id": "' || CAST(:id AS text) || '"}' AS json),
                    'processing', 'migration-progress-job-' || :id, 1, 3
                )
            """),
            {"id": job_id},
        )
    return job_id


async def _insert_progress(database_engine, *, job_id: str, **overrides) -> None:
    from app.auth.tables import enrichment_job_progress

    row = {
        "job_id": job_id,
        "policy_version": 1,
        "required_aspects": ["light_exposure"],
        "local_covered_aspects": [],
        "persisted_covered_aspects": ["light_exposure"],
        "indexed_covered_aspects": [],
        "final_judged_covered_aspects": ["light_exposure"],
        "final_judged_missing_aspects": [],
        "answerability_status": "full",
        "acquisition_avoided": False,
        "search_count": 2,
        "accepted_aspect_count": 1,
        "last_validation_run_id": None,
        **overrides,
    }
    async with database_engine.begin() as connection:
        await connection.execute(
            insert(enrichment_job_progress).values(**row)
        )


def _constraint_names() -> set[str]:
    return {
        "ck_enrichment_job_progress_policy_version",
        "ck_enrichment_job_progress_answerability_status",
        "ck_enrichment_job_progress_search_count",
        "ck_enrichment_job_progress_accepted_aspect_count",
    }


async def test_upgrade_0012_to_0013_creates_progress_table_with_closed_constraints() -> None:
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

        await _run_alembic(database_url, "0012_durable_enrichment")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        # Telemetry table exists and is untouched before migration 0013.
        async with database_engine.connect() as connection:
            telemetry_exists = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = 'enrichment_telemetry_observations'
                """)
            )
            assert telemetry_exists == 1
            progress_exists = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = 'enrichment_job_progress'
                """)
            )
            assert progress_exists == 0

        await _run_alembic(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        async with database_engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            assert revision == "0013_enrichment_job_progress"
            constraint_names = set(
                (
                    await connection.execute(
                        text("""
                            SELECT constraint_name
                            FROM information_schema.table_constraints
                            WHERE table_name = 'enrichment_job_progress'
                        """)
                    )
                ).scalars().all()
            )
            assert _constraint_names() <= constraint_names
            columns = set(
                (
                    await connection.execute(
                        text("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = 'enrichment_job_progress'
                        """)
                    )
                ).scalars().all()
            )
            assert {
                "job_id",
                "policy_version",
                "required_aspects",
                "local_covered_aspects",
                "persisted_covered_aspects",
                "indexed_covered_aspects",
                "final_judged_covered_aspects",
                "final_judged_missing_aspects",
                "answerability_status",
                "acquisition_avoided",
                "search_count",
                "accepted_aspect_count",
                "last_validation_run_id",
                "created_at",
                "updated_at",
            } <= columns

        job_id = await _create_job(database_engine)
        await _insert_progress(database_engine, job_id=job_id)

        # Migration 0012 telemetry tables still function: a terminal job with
        # exactly one matching observation commits normally after 0013.
        terminal_job_id = await _create_job(database_engine)
        async with database_engine.begin() as connection:
            await connection.execute(
                text("""
                    UPDATE application_jobs
                    SET status = 'failed', completed_at = NOW()
                    WHERE id = CAST(:job_id AS uuid)
                """),
                {"job_id": terminal_job_id},
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
                        CAST(:job_id AS uuid), '1', 'failed',
                        false, 1, 1, 0, 1, 0, 0.0
                    )
                """),
                {"job_id": terminal_job_id},
            )
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


async def test_progress_requires_existing_job_and_rejects_invalid_values() -> None:
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

        await _run_alembic(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        with pytest.raises(IntegrityError):
            await _insert_progress(database_engine, job_id=str(uuid4()))

        job_id = await _create_job(database_engine)

        # Zero policy version is rejected.
        with pytest.raises(IntegrityError):
            await _insert_progress(database_engine, job_id=job_id, policy_version=0)

        # Negative search count is rejected.
        with pytest.raises(IntegrityError):
            await _insert_progress(database_engine, job_id=job_id, search_count=-1)

        # Unbounded search count is rejected.
        with pytest.raises(IntegrityError):
            await _insert_progress(database_engine, job_id=job_id, search_count=101)

        # Unbounded accepted count is rejected.
        with pytest.raises(IntegrityError):
            await _insert_progress(database_engine, job_id=job_id, accepted_aspect_count=101)

        # Unclosed answerability status is rejected.
        with pytest.raises(IntegrityError):
            await _insert_progress(
                database_engine, job_id=job_id, answerability_status="mystery"
            )

        # Valid row with null final judging succeeds.
        await _insert_progress(
            database_engine,
            job_id=job_id,
            final_judged_covered_aspects=None,
            final_judged_missing_aspects=None,
            answerability_status=None,
            last_validation_run_id=None,
        )
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


async def test_downgrade_0013_drops_progress_table() -> None:
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

        await _run_alembic(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        async with database_engine.connect() as connection:
            exists = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = 'enrichment_job_progress'
                """)
            )
            assert exists == 1

        await _run_alembic_downgrade(database_url, "0012_durable_enrichment")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        async with database_engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            assert revision == "0012_durable_enrichment"
            exists = await connection.scalar(
                text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = 'enrichment_job_progress'
                """)
            )
            assert exists == 0
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()
