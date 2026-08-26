"""Migration 0020: durable refresh-enrichment causal association.

Verifies the real migration creates `profile_refresh_enrichment_jobs` with a
composite primary key, cascade-deleting foreign keys, and an enrichment-side
index; that duplicate pairs are rejected by the composite key; that deleting
either job cascades to the association; and that downgrade removes the table
cleanly.
"""

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
from sqlalchemy.ext.asyncio import create_async_engine

from .conftest import BASE_DATABASE_URL

BACKEND_ROOT = Path(__file__).resolve().parents[2]

PK_COLUMNS_SQL = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.table_name = 'profile_refresh_enrichment_jobs'
  AND tc.constraint_type = 'PRIMARY KEY'
ORDER BY kcu.ordinal_position
"""

INDEXES_SQL = """
SELECT indexname FROM pg_indexes
WHERE tablename = 'profile_refresh_enrichment_jobs'
"""

COUNT_ASSOCIATIONS_SQL = (
    "SELECT count(*) FROM profile_refresh_enrichment_jobs"
)

TABLE_EXISTS_SQL = """
SELECT table_name FROM information_schema.tables
WHERE table_name = 'profile_refresh_enrichment_jobs'
"""

INSERT_ASSOCIATION_SQL = """
INSERT INTO profile_refresh_enrichment_jobs (
    refresh_job_id, enrichment_job_id
) VALUES (CAST(:r AS uuid), CAST(:e AS uuid))
"""


async def _run_alembic(database_url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _fresh_database() -> tuple[str, object, str]:
    database_name = f"migration_{uuid4().hex}"
    admin_engine = create_async_engine(
        BASE_DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=False,
    )
    database_url = (
        make_url(BASE_DATABASE_URL)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    return database_name, admin_engine, database_url


async def _seed_job_pair(
    database_engine, *, refresh_id: str, enrichment_id: str
) -> None:
    async with database_engine.begin() as connection:
        for job_id, job_type in (
            (enrichment_id, "enrich_confirmed_plant"),
            (refresh_id, "refresh_profile"),
        ):
            await connection.execute(
                text(
                    """
                    INSERT INTO application_jobs (
                        id, job_type, payload_version, payload, status,
                        idempotency_key, attempt_count, max_attempts
                    ) VALUES (
                        CAST(:id AS uuid), :job_type, 1, '{}'::json,
                        'pending', :idem, 1, 3
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": job_id, "job_type": job_type, "idem": f"job-{job_id}"},
            )


async def _scalar(database_engine, sql: str):
    async with database_engine.connect() as connection:
        return (await connection.execute(text(sql))).scalar()


async def test_migration_0020_upgrade_downgrade_and_constraints() -> None:
    database_name, admin_engine, database_url = await _fresh_database()
    engine = None
    try:
        await _run_alembic(database_url, "upgrade", "0019_manual_plant_search")
        await _run_alembic(database_url, "upgrade", "head")
        engine = create_async_engine(database_url, pool_pre_ping=False)

        # Composite primary key covers both columns.
        async with engine.connect() as connection:
            pk = (
                await connection.execute(text(PK_COLUMNS_SQL))
            ).scalars().all()
        assert set(pk) == {"refresh_job_id", "enrichment_job_id"}

        # Enrichment-side index exists.
        async with engine.connect() as connection:
            indexes = (
                await connection.execute(text(INDEXES_SQL))
            ).scalars().all()
        assert any("enrichment_id" in name for name in indexes)

        refresh_id = str(uuid4())
        enrichment_id = str(uuid4())
        await _seed_job_pair(
            engine, refresh_id=refresh_id, enrichment_id=enrichment_id
        )

        async with engine.begin() as connection:
            await connection.execute(
                text(INSERT_ASSOCIATION_SQL),
                {"r": refresh_id, "e": enrichment_id},
            )
        assert await _scalar(engine, COUNT_ASSOCIATIONS_SQL) == 1

        # Duplicate pair rejected by the composite primary key.
        with pytest.raises(Exception):
            async with engine.begin() as connection:
                await connection.execute(
                    text(INSERT_ASSOCIATION_SQL),
                    {"r": refresh_id, "e": enrichment_id},
                )
        assert await _scalar(engine, COUNT_ASSOCIATIONS_SQL) == 1

        # Deleting the enrichment job cascades.
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM application_jobs WHERE id = CAST(:e AS uuid)"),
                {"e": enrichment_id},
            )
        assert await _scalar(engine, COUNT_ASSOCIATIONS_SQL) == 0

        # Deleting the refresh job cascades too.
        second_enrichment = str(uuid4())
        await _seed_job_pair(
            engine, refresh_id=refresh_id, enrichment_id=second_enrichment
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(INSERT_ASSOCIATION_SQL),
                {"r": refresh_id, "e": second_enrichment},
            )
            await connection.execute(
                text("DELETE FROM application_jobs WHERE id = CAST(:r AS uuid)"),
                {"r": refresh_id},
            )
        assert await _scalar(engine, COUNT_ASSOCIATIONS_SQL) == 0

        await engine.dispose()
        engine = None

        await _run_alembic(database_url, "downgrade", "-1")
        engine = create_async_engine(database_url, pool_pre_ping=False)
        tables = []
        async with engine.connect() as connection:
            tables = (
                await connection.execute(text(TABLE_EXISTS_SQL))
            ).scalars().all()
        assert tables == []
    finally:
        if engine is not None:
            await engine.dispose()
        cleanup = create_async_engine(
            BASE_DATABASE_URL, isolation_level="AUTOCOMMIT"
        )
        try:
            async with cleanup.connect() as connection:
                await connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}"')
                )
        finally:
            await cleanup.dispose()
