"""Migration 0015: shared persistent limiter state.

Verifies the real migration creates the ``auth_limiter_state`` table with its
uniqueness constraints, closed category/dimension checks, count bounds, and
expiry index, and that downgrade removes the table cleanly.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
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


async def _inspect_schema(database_url: str) -> dict:
    engine = create_async_engine(database_url, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:

            def _collect(sync_conn) -> dict:
                inspector = inspect(sync_conn)
                tables = set(inspector.get_table_names())
                if "auth_limiter_state" not in tables:
                    return {"tables": tables, "unique": set(), "constraints": set()}
                return {
                    "tables": tables,
                    "unique": {
                        index["name"]
                        for index in inspector.get_indexes("auth_limiter_state")
                    },
                    "constraints": {
                        constraint["name"]
                        for constraint in inspector.get_check_constraints("auth_limiter_state")
                    },
                }

            return await conn.run_sync(_collect)
    finally:
        await engine.dispose()


async def test_migration_0015_upgrade_and_downgrade() -> None:
    database_name = f"migration_limiter_{uuid4().hex}"
    admin_engine = create_async_engine(
        BASE_DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=False,
    )
    database_url = make_url(BASE_DATABASE_URL).set(database=database_name).render_as_string(
        hide_password=False
    )
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database_name}"'))

    try:
        await _run_alembic(database_url, "head")

        schema = await _inspect_schema(database_url)
        assert "auth_limiter_state" in schema["tables"]
        assert "uq_auth_limiter_state_dimension_category_key_window" in schema["unique"]
        assert "ix_auth_limiter_state_window_end" in schema["unique"]
        assert "ck_auth_limiter_state_dimension" in schema["constraints"]
        assert "ck_auth_limiter_state_category" in schema["constraints"]
        assert "ck_auth_limiter_state_count" in schema["constraints"]
        assert "ck_auth_limiter_state_window" in schema["constraints"]

        engine = create_async_engine(database_url, pool_pre_ping=False)
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO auth_limiter_state
                            (id, dimension, category, digest_key, window_start, window_end, count)
                        VALUES
                            (:id, 'source', 'registration',
                             repeat('a', 64), now(), now() + interval '1 hour', 1)
                        """
                    ),
                    {"id": str(uuid4())},
                )
                await conn.commit()
        finally:
            await engine.dispose()

        await _run_alembic_downgrade(database_url, "0014_profile_canonical_identity")

        schema = await _inspect_schema(database_url)
        assert "auth_limiter_state" not in schema["tables"]
    finally:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        await admin_engine.dispose()
