from __future__ import annotations

import asyncio
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


async def test_upgrade_0009_to_0010_preserves_rows_and_scopes_active_uniqueness() -> None:
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

        await _run_alembic(database_url, "0009_durable_background_jobs")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        document_id = uuid4()
        legacy_job_id = uuid4()
        async with database_engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO knowledge_documents (
                        id, scientific_name, topic, title, content, confidence, review_status
                    ) VALUES (
                        CAST(:id AS uuid), 'Monstera deliciosa', 'watering',
                        'Legacy evidence', 'Preserve this content', 0.9, 'approved'
                    )
                """),
                {"id": str(document_id)},
            )
            await connection.execute(
                text("""
                    INSERT INTO application_jobs (
                        id, job_type, payload_version, payload, status,
                        idempotency_key, max_attempts
                    ) VALUES (
                        CAST(:id AS uuid), 'ingest_validated_claims', 1,
                        CAST('{}' AS json), 'complete', 'legacy-run', 1
                    )
                """),
                {"id": str(legacy_job_id)},
            )
        await database_engine.dispose()
        database_engine = None

        await _run_alembic(database_url, "0010_enrichment_persistence")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        active_job_id = uuid4()
        async with database_engine.begin() as connection:
            assert await connection.scalar(
                text("SELECT content FROM knowledge_documents WHERE id = CAST(:id AS uuid)"),
                {"id": str(document_id)},
            ) == "Preserve this content"
            assert await connection.scalar(
                text("SELECT idempotency_key FROM application_jobs WHERE id = CAST(:id AS uuid)"),
                {"id": str(legacy_job_id)},
            ) == "legacy-run"
            await connection.execute(
                text("""
                    INSERT INTO application_jobs (
                        id, job_type, payload_version, payload, status, idempotency_key,
                        active_deduplication_key, max_attempts
                    ) VALUES (
                        CAST(:id AS uuid), 'enrich_confirmed_plant', 1,
                        CAST('{}' AS json), 'pending', 'run-one', 'species-policy-one', 3
                    )
                """),
                {"id": str(active_job_id)},
            )

        with pytest.raises(IntegrityError):
            async with database_engine.begin() as connection:
                await connection.execute(
                    text("""
                        INSERT INTO application_jobs (
                            id, job_type, payload_version, payload, status, idempotency_key,
                            active_deduplication_key, max_attempts
                        ) VALUES (
                            CAST(:id AS uuid), 'enrich_confirmed_plant', 1,
                            CAST('{}' AS json), 'processing', 'run-two',
                            'species-policy-one', 3
                        )
                    """),
                    {"id": str(uuid4())},
                )

        async with database_engine.begin() as connection:
            await connection.execute(
                text("UPDATE application_jobs SET status = 'complete' WHERE id = CAST(:id AS uuid)"),
                {"id": str(active_job_id)},
            )
            await connection.execute(
                text("""
                    INSERT INTO application_jobs (
                        id, job_type, payload_version, payload, status, idempotency_key,
                        active_deduplication_key, max_attempts
                    ) VALUES (
                        CAST(:id AS uuid), 'enrich_confirmed_plant', 1,
                        CAST('{}' AS json), 'pending', 'run-three', 'species-policy-one', 3
                    )
                """),
                {"id": str(uuid4())},
            )
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                (
                    await connection.execute(
                        text("""
                            SELECT table_name FROM information_schema.tables
                            WHERE table_schema = current_schema()
                        """)
                    )
                ).scalars()
            )

        assert revision == "0010_enrichment_persistence"
        assert {
            "candidate_enrichment_jobs",
            "taxonomy_provenance_snapshots",
            "knowledge_document_aspect_supports",
            "enrichment_validation_runs",
        } <= tables
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        finally:
            await admin_engine.dispose()
