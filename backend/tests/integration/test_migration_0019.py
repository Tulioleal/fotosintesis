"""Migration 0019: manual plant search candidate origin and ownership.

Verifies the real migration makes `identification_candidates.identification_id`
nullable, adds the `origin` column defaulting to `image_identification`, and
adds a nullable `user_id` FK to `users`. Existing image rows keep their
`origin=image_identification` and null `user_id` without any backfill, manual
candidates can be inserted with a null `identification_id` and a `user_id`, and
downgrade removes the new columns cleanly.
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


async def _test_database_url() -> tuple[str, object, str]:
    database_name = f"migration_{uuid4().hex}"
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
    return database_name, admin_engine, database_url


async def _insert_image_candidate(
    database_engine, *, user_id: str, candidate_id: str
) -> None:
    image_id = str(uuid4())
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (id, name, email, email_verified)
                VALUES (CAST(:id AS uuid), 'Tester', :email, true)
                """
            ),
            {"id": user_id, "email": f"{user_id}@test.invalid"},
        )
        await connection.execute(
            text(
                """
                INSERT INTO identification_images (
                    id, user_id, storage_path, mime_type, size_bytes,
                    status, created_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:user_id AS uuid), '/img', 'image/jpeg',
                    10, 'complete', NOW()
                )
                """
            ),
            {"id": image_id, "user_id": user_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO identification_candidates (
                    id, identification_id, suggested_scientific_name,
                    confidence_label, visible_traits, possible_match_copy,
                    validation_status, created_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:image_id AS uuid),
                    'Monstera deliciosa', 'high', '[]'::json, 'match',
                    'validated', NOW()
                )
                """
            ),
            {"id": candidate_id, "image_id": image_id},
        )


async def _columns(database_engine, table: str) -> set[str]:
    async with database_engine.connect() as connection:
        rows = await connection.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = :table
                """
            ),
            {"table": table},
        )
        return set(rows.scalars().all())


async def test_upgrade_0018_to_0019_adds_origin_and_nullable_owner() -> None:
    database_name, admin_engine, database_url = await _test_database_url()
    database_engine = None
    try:
        await _run_alembic(database_url, "0018_profile_section_versions")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        user_id = str(uuid4())
        candidate_id = str(uuid4())
        await _insert_image_candidate(
            database_engine, user_id=user_id, candidate_id=candidate_id
        )

        await _run_alembic(database_url, "0019_manual_plant_search")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        columns = await _columns(database_engine, "identification_candidates")
        assert {"origin", "user_id"} <= columns

        async with database_engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT origin, user_id, identification_id
                        FROM identification_candidates
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"id": candidate_id},
                )
            ).first()
            # Existing rows keep the image default and null ownership, no backfill.
            assert row.origin == "image_identification"
            assert row.user_id is None
            assert row.identification_id is not None

            # A manual candidate can be inserted with a null identification_id
            # and a user_id owner.
            manual_user_id = str(uuid4())
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id, name, email, email_verified)
                    VALUES (CAST(:id AS uuid), 'Manual', :email, true)
                    """
                ),
                {"id": manual_user_id, "email": f"{manual_user_id}@test.invalid"},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO identification_candidates (
                        id, origin, user_id, identification_id,
                        suggested_scientific_name, confidence_label,
                        visible_traits, possible_match_copy,
                        validation_status, created_at
                    ) VALUES (
                        CAST(:id AS uuid), 'manual_search', CAST(:user_id AS uuid),
                        NULL, 'Monstera deliciosa', 'manual',
                        '[]'::json, 'match', 'validated', NOW()
                    )
                    """
                ),
                {"id": str(uuid4()), "user_id": manual_user_id},
            )
            await connection.commit()

        async with database_engine.connect() as connection:
            manual = (
                await connection.execute(
                    text(
                        """
                        SELECT origin, user_id, identification_id, confidence_label
                        FROM identification_candidates
                        WHERE origin = 'manual_search'
                        """
                    )
                )
            ).first()
            assert manual is not None
            assert manual.origin == "manual_search"
            assert manual.user_id is not None
            assert manual.identification_id is None
            assert manual.confidence_label == "manual"
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


async def test_downgrade_0019_removes_origin_and_owner() -> None:
    database_name, admin_engine, database_url = await _test_database_url()
    database_engine = None
    try:
        await _run_alembic(database_url, "0019_manual_plant_search")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        columns = await _columns(database_engine, "identification_candidates")
        assert {"origin", "user_id"} <= columns

        await _run_alembic_downgrade(database_url, "0018_profile_section_versions")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        columns = await _columns(database_engine, "identification_candidates")
        assert "origin" not in columns
        assert "user_id" not in columns

        async with database_engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT is_nullable FROM information_schema.columns
                        WHERE table_name = 'identification_candidates'
                          AND column_name = 'identification_id'
                        """
                    )
                )
            ).first()
            assert row.is_nullable == "NO"
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()
