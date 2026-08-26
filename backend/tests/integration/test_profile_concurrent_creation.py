"""Real PostgreSQL concurrent canonical profile creation convergence.

Proves that two independent sessions requesting the same canonical species
profile converge on one profile row without surfacing an IntegrityError,
using the real unique-key race under PostgreSQL instead of monkeypatching.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.auth.tables import plant_profiles
from app.profile_garden.repository import PlantProfileGardenRepository

SPECIES_NAME = "Monstera deliciosa"
SPECIES_KEY = "gbif:2878688|binomial:Monstera deliciosa"


async def _create_profile_with_session(session_factory):
    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        return await repo.get_or_create_profile(
            scientific_name=SPECIES_NAME,
            common_name="Monstera",
            accepted_gbif_key=2878688,
            normalized_binomial=SPECIES_NAME,
            canonical_species_key=SPECIES_KEY,
        )


async def _count_canonical_profiles(session_factory) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(plant_profiles)
                .where(plant_profiles.c.canonical_species_key == SPECIES_KEY)
            )
            or 0
        )


async def test_real_concurrent_profile_creation_converges_on_one_row(
    pg_session_factory,
) -> None:
    """Two independent sessions racing to create the same canonical profile
    converge on the same profile id, leave exactly one canonical row, and
    neither request surfaces an IntegrityError."""
    assert await _count_canonical_profiles(pg_session_factory) == 0

    first, second = await asyncio.gather(
        _create_profile_with_session(pg_session_factory),
        _create_profile_with_session(pg_session_factory),
    )

    assert first.id == second.id
    assert await _count_canonical_profiles(pg_session_factory) == 1
