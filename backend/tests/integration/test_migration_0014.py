"""Migration 0014: canonical species identity on plant profiles.

Verifies the real migration adds the canonical identity columns and partial
unique index, backfills only unambiguous profiles through confirmed garden
candidates, leaves ambiguous or identity-less profiles null, reports
duplicate-profile conflicts instead of merging, and downgrades cleanly.
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


async def _create_user(database_engine) -> str:
    user_id = str(uuid4())
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
    return user_id


async def _create_identification(
    database_engine,
    *,
    user_id: str,
    gbif_accepted_key: int | None,
    binomial_name: str | None,
    validation_status: str = "validated",
    confirmed: bool = True,
) -> str:
    image_id = str(uuid4())
    candidate_id = str(uuid4())
    async with database_engine.begin() as connection:
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
                    gbif_key, gbif_accepted_key, accepted_scientific_name,
                    binomial_name, taxonomic_status, synonyms,
                    validation_status, confirmed_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:image_id AS uuid),
                    'Monstera deliciosa', 'high', '[]'::json,
                    'match', :gbif_key, :gbif_accepted_key,
                    'Monstera deliciosa', :binomial_name, 'accepted',
                    '[]'::json, :validation_status,
                    CASE WHEN :confirmed THEN NOW() ELSE NULL END
                )
                """
            ),
            {
                "id": candidate_id,
                "image_id": image_id,
                "gbif_key": gbif_accepted_key,
                "gbif_accepted_key": gbif_accepted_key,
                "binomial_name": binomial_name,
                "validation_status": validation_status,
                "confirmed": confirmed,
            },
        )
    return candidate_id


async def _create_profile_with_garden(
    database_engine, *, candidate_id: str, user_id: str,
    scientific_name: str = "Monstera deliciosa",
) -> str:
    profile_id = str(uuid4())
    garden_id = str(uuid4())
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO plant_profiles (
                    id, scientific_name, common_name, aliases, sections,
                    sources, confidence, limitations, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), :scientific_name, 'Swiss cheese plant',
                    '[]'::json, '{}'::json, '[]'::json, 0.5, '[]'::json,
                    NOW(), NOW()
                )
                """
            ),
            {"id": profile_id, "scientific_name": scientific_name},
        )
        await connection.execute(
            text(
                """
                INSERT INTO garden_plants (
                    id, user_id, profile_id, confirmed_candidate_id,
                    active_reminders, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), :user_id, CAST(:profile_id AS uuid),
                    CAST(:candidate_id AS uuid), 0, NOW(), NOW()
                )
                """
            ),
            {
                "id": garden_id,
                "user_id": user_id,
                "profile_id": profile_id,
                "candidate_id": candidate_id,
            },
        )
    return profile_id


async def _canonical(database_engine, *, profile_id: str) -> dict:
    async with database_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT canonical_species_key, normalized_binomial, accepted_gbif_key
                    FROM plant_profiles
                    WHERE id = CAST(:id AS uuid)
                    """
                ),
                {"id": profile_id},
            )
        ).first()
    return dict(row._mapping)


async def _unique_index_exists(database_engine) -> bool:
    async with database_engine.connect() as connection:
        value = await connection.scalar(
            text(
                """
                SELECT COUNT(*) FROM pg_indexes
                WHERE tablename = 'plant_profiles'
                  AND indexname = 'uq_plant_profiles_canonical_species_key'
                  AND indexdef LIKE '%UNIQUE%'
                """
            )
        )
    return bool(value)


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


async def test_upgrade_0013_to_0014_backfills_only_unambiguous_profiles() -> None:
    database_name, admin_engine, database_url = await _test_database_url()
    database_engine = None
    try:
        await _run_alembic(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        user_id = await _create_user(database_engine)
        unambiguous_candidate = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=2878688,
            binomial_name="Monstera deliciosa",
        )
        no_identity_candidate = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=None,
            binomial_name=None,
        )
        ambiguous_a = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=1,
            binomial_name="Monstera deliciosa",
        )
        ambiguous_b = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=2,
            binomial_name="Monstera deliciosa",
        )
        # A zero GBIF key is invalid under the runtime positive-key rule, so
        # the profile must stay un-backfilled even with a valid binomial.
        invalid_key_candidate = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=0,
            binomial_name="Monstera deliciosa",
        )
        # A valid candidate that will share a profile with the invalid-key
        # candidate; the profile must remain unmodified because one of its
        # confirmed, validated candidates cannot derive a canonical identity.
        mixed_valid_candidate = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=3,
            binomial_name="Monstera deliciosa",
        )

        unambiguous_profile = await _create_profile_with_garden(
            database_engine, candidate_id=unambiguous_candidate, user_id=user_id,
            scientific_name="Monstera deliciosa",
        )
        no_identity_profile = await _create_profile_with_garden(
            database_engine, candidate_id=no_identity_candidate, user_id=user_id,
            scientific_name="Monstera deliciosa f. borsigiana",
        )
        ambiguous_profile = await _create_profile_with_garden(
            database_engine, candidate_id=ambiguous_a, user_id=user_id,
            scientific_name="Monstera deliciosa subsp. sierrana",
        )
        invalid_key_profile = await _create_profile_with_garden(
            database_engine, candidate_id=invalid_key_candidate, user_id=user_id,
            scientific_name="Monstera deliciosa subsp. obliqua",
        )
        mixed_profile = await _create_profile_with_garden(
            database_engine, candidate_id=mixed_valid_candidate, user_id=user_id,
            scientific_name="Monstera deliciosa mixed fixture",
        )
        # A second garden link makes the same profile ambiguous (two keys).
        async with database_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO garden_plants (
                        id, user_id, profile_id, confirmed_candidate_id,
                        active_reminders, created_at, updated_at
                    ) VALUES (
                        CAST(:id AS uuid), :user_id, CAST(:profile_id AS uuid),
                        CAST(:candidate_id AS uuid), 0, NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "profile_id": ambiguous_profile,
                    "candidate_id": ambiguous_b,
                },
            )
            # A second garden link from the mixed profile to the invalid-key
            # candidate; the profile is ambiguous because one confirmed,
            # validated candidate cannot derive a canonical identity.
            await connection.execute(
                text(
                    """
                    INSERT INTO garden_plants (
                        id, user_id, profile_id, confirmed_candidate_id,
                        active_reminders, created_at, updated_at
                    ) VALUES (
                        CAST(:id AS uuid), :user_id, CAST(:profile_id AS uuid),
                        CAST(:candidate_id AS uuid), 0, NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "profile_id": mixed_profile,
                    "candidate_id": invalid_key_candidate,
                },
            )

        await _run_alembic(database_url, "0014_profile_canonical_identity")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        unambiguous = await _canonical(database_engine, profile_id=unambiguous_profile)
        assert unambiguous["canonical_species_key"] == "gbif:2878688|binomial:Monstera deliciosa"
        assert unambiguous["normalized_binomial"] == "Monstera deliciosa"
        assert unambiguous["accepted_gbif_key"] == 2878688

        no_identity = await _canonical(database_engine, profile_id=no_identity_profile)
        assert no_identity["canonical_species_key"] is None
        assert no_identity["normalized_binomial"] is None

        ambiguous = await _canonical(database_engine, profile_id=ambiguous_profile)
        assert ambiguous["canonical_species_key"] is None
        assert ambiguous["normalized_binomial"] is None

        invalid_key = await _canonical(database_engine, profile_id=invalid_key_profile)
        assert invalid_key["canonical_species_key"] is None
        assert invalid_key["normalized_binomial"] is None
        assert invalid_key["accepted_gbif_key"] is None

        mixed = await _canonical(database_engine, profile_id=mixed_profile)
        assert mixed["canonical_species_key"] is None
        assert mixed["normalized_binomial"] is None
        assert mixed["accepted_gbif_key"] is None

        assert await _unique_index_exists(database_engine)
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


async def test_upgrade_reports_duplicate_profile_conflict() -> None:
    database_name, admin_engine, database_url = await _test_database_url()
    database_engine = None
    try:
        await _run_alembic(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)

        user_id = await _create_user(database_engine)
        candidate = await _create_identification(
            database_engine,
            user_id=user_id,
            gbif_accepted_key=2878688,
            binomial_name="Monstera deliciosa",
        )
        await _create_profile_with_garden(
            database_engine, candidate_id=candidate, user_id=user_id,
            scientific_name="Monstera deliciosa",
        )
        await _create_profile_with_garden(
            database_engine, candidate_id=candidate, user_id=user_id,
            scientific_name="Monstera deliciosa var. borsigiana",
        )

        env = {**os.environ, "DATABASE_URL": database_url}
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "upgrade", "0014_profile_canonical_identity"],
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "conflict" in (result.stdout + result.stderr).casefold()
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()


async def test_downgrade_0014_removes_canonical_columns() -> None:
    database_name, admin_engine, database_url = await _test_database_url()
    database_engine = None
    try:
        await _run_alembic(database_url, "0014_profile_canonical_identity")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        async with database_engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'plant_profiles'
                            """
                        )
                    )
                ).scalars().all()
            )
            assert {"accepted_gbif_key", "normalized_binomial", "canonical_species_key"} <= columns

        await _run_alembic_downgrade(database_url, "0013_enrichment_job_progress")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        async with database_engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            assert revision == "0013_enrichment_job_progress"
            columns = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'plant_profiles'
                            """
                        )
                    )
                ).scalars().all()
            )
            assert "canonical_species_key" not in columns
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        await admin_engine.dispose()
