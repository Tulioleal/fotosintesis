from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import identification_candidates, identification_images, plant_profiles
from app.main import app


@pytest.mark.asyncio
async def test_confirmed_candidate_can_create_profile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, candidate_id = await _create_user_candidate(
        session_factory,
        email="fern@example.com",
        accepted_scientific_name="Nephrolepis exaltata",
        confirmed=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["scientific_name"] == "Nephrolepis exaltata"
    assert response.json()["common_name"] == "Helecho"

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(plant_profiles))
    assert total == 1


@pytest.mark.asyncio
async def test_profile_exposes_canonical_identity_and_reuses_profile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, candidate_id = await _create_user_candidate(
        session_factory,
        email="canonical@example.com",
        accepted_scientific_name="Monstera deliciosa",
        gbif_accepted_key=2878688,
        binomial_name="Monstera deliciosa",
        confirmed=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get(
            f"/plant-profiles/Monstera%20deliciosa?candidateId={candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        second = await client.get(
            f"/plant-profiles/Monstera%20deliciosa?candidateId={candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert first.status_code == 200
    body = first.json()
    assert body["accepted_gbif_key"] == 2878688
    assert body["binomial_name"] == "Monstera deliciosa"
    assert body["canonical_species_key"] == "gbif:2878688|binomial:Monstera deliciosa"
    assert second.json()["id"] == body["id"]

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(plant_profiles))
    assert total == 1


@pytest.mark.asyncio
async def test_profile_preserves_accepted_display_name_separately_from_binomial(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The accepted display name (with author authority) and the canonical
    binomial are separate: the profile stores and returns both, and the
    canonical species key is derived only from the binomial plus GBIF key."""
    accepted_display = "Monstera deliciosa Liebm."
    binomial = "Monstera deliciosa"
    token, candidate_id = await _create_user_candidate(
        session_factory,
        email="display-name@example.com",
        accepted_scientific_name=accepted_display,
        gbif_accepted_key=2878688,
        binomial_name=binomial,
        confirmed=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/plant-profiles/{accepted_display.replace(' ', '%20')}?candidateId={candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scientific_name"] == accepted_display
    assert body["binomial_name"] == binomial
    assert body["accepted_gbif_key"] == 2878688
    assert body["canonical_species_key"] == "gbif:2878688|binomial:Monstera deliciosa"

    async with session_factory() as session:
        row = (
            await session.execute(
                select(plant_profiles).where(plant_profiles.c.canonical_species_key == "gbif:2878688|binomial:Monstera deliciosa")
            )
        ).first()
    assert row is not None
    assert row.scientific_name == accepted_display
    assert row.normalized_binomial == binomial
    assert row.accepted_gbif_key == 2878688
    assert row.canonical_species_key == "gbif:2878688|binomial:Monstera deliciosa"


@pytest.mark.asyncio
async def test_concurrent_canonical_profile_creation_converges_on_one_profile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When canonical profile creation loses the unique-key race, the retry
    reselects the winning profile so concurrent requests converge on one row
    instead of surfacing an API failure."""
    from app.profile_garden.repository import PlantProfileGardenRepository

    # Seed the winning canonical profile through a real request.
    token, candidate_id = await _create_user_candidate(
        session_factory,
        email="concurrent@example.com",
        accepted_scientific_name="Monstera deliciosa",
        gbif_accepted_key=2878688,
        binomial_name="Monstera deliciosa",
        confirmed=True,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seeded = await client.get(
            f"/plant-profiles/Monstera%20deliciosa?candidateId={candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert seeded.status_code == 200
    winner_id = seeded.json()["id"]

    # Simulate the losing concurrent creation: the first lookups miss the
    # winner (as if it committed after the read), so _create_profile hits the
    # unique-key race and the retry reselects the winning profile.
    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        original_find = repo._find_profile
        attempts = {"n": 0}

        async def find_once(**kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return None
            return await original_find(**kwargs)

        repo._find_profile = find_once  # type: ignore[method-assign]
        result = await repo.get_or_create_profile(
            scientific_name="Monstera deliciosa",
            common_name="Helecho",
            accepted_gbif_key=2878688,
            normalized_binomial="Monstera deliciosa",
            canonical_species_key="gbif:2878688|binomial:Monstera deliciosa",
        )

    assert str(result.id) == winner_id
    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(plant_profiles))
    assert total == 1


@pytest.mark.asyncio
async def test_profile_requires_authenticated_confirmed_candidate_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, unconfirmed_id = await _create_user_candidate(
        session_factory,
        email="unconfirmed@example.com",
        accepted_scientific_name="Nephrolepis exaltata",
        confirmed=False,
    )
    _, wrong_user_candidate_id = await _create_user_candidate(
        session_factory,
        email="other@example.com",
        accepted_scientific_name="Nephrolepis exaltata",
        confirmed=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthenticated = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={unconfirmed_id}"
        )
        missing_candidate = await client.get(
            "/plant-profiles/Nephrolepis%20exaltata",
            headers={"Authorization": f"Bearer {token}"},
        )
        unconfirmed = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={unconfirmed_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        wrong_user = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={wrong_user_candidate_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert unauthenticated.status_code == 401
    assert missing_candidate.status_code == 422
    assert unconfirmed.status_code == 409
    assert wrong_user.status_code == 409

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(plant_profiles))
    assert total == 0


@pytest.mark.asyncio
async def test_profile_rejects_unvalidated_candidate_and_name_mismatch(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, unvalidated_id = await _create_user_candidate(
        session_factory,
        email="pending@example.com",
        accepted_scientific_name=None,
        validation_status="manual_review",
        confirmed=True,
    )
    mismatch_token, mismatch_id = await _create_user_candidate(
        session_factory,
        email="mismatch@example.com",
        accepted_scientific_name="Monstera deliciosa",
        confirmed=True,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unvalidated = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={unvalidated_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        mismatch = await client.get(
            f"/plant-profiles/Nephrolepis%20exaltata?candidateId={mismatch_id}",
            headers={"Authorization": f"Bearer {mismatch_token}"},
        )

    assert unvalidated.status_code == 409
    assert mismatch.status_code == 409

    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(plant_profiles))
    assert total == 0


@pytest.mark.asyncio
async def test_ambiguous_null_key_legacy_profile_is_not_adopted_by_display_name(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A null-key legacy profile is never adopted or mutated at runtime based
    on display-name equality: the lookup only resolves canonical keys, and a
    candidate without a canonical identity keeps the legacy display-name
    path. Legacy null-key rows stay byte-for-byte unchanged."""
    from app.profile_garden.repository import PlantProfileGardenRepository

    legacy_profile_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(plant_profiles).values(
                id=legacy_profile_id,
                scientific_name="Monstera deliciosa",
                common_name="Monstera",
                aliases=[],
                sections={"care": ["Legacy snapshot content."]},
                sources=[],
                confidence=0.5,
                limitations=[],
            )
        )
        await session.commit()

    # A confirmed candidate with a canonical identity must not resolve to the
    # display-name-matching legacy profile: the canonical lookup misses it.
    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        existing = await repo._find_profile(
            scientific_name="Monstera deliciosa",
            normalized_binomial="Monstera deliciosa",
            canonical_species_key="gbif:2878688|binomial:Monstera deliciosa",
        )
        assert existing is None
        assert await repo._get_profile_row_by_id(legacy_profile_id) is not None

    # The legacy profile remains null-key and unchanged.
    async with session_factory() as session:
        row = (
            await session.execute(
                select(plant_profiles).where(plant_profiles.c.id == legacy_profile_id)
            )
        ).first()
    assert row.canonical_species_key is None
    assert row.normalized_binomial is None
    assert row.accepted_gbif_key is None
    assert row.sections == {"care": ["Legacy snapshot content."]}


async def _create_user_candidate(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    accepted_scientific_name: str | None,
    validation_status: str = "validated",
    confirmed: bool,
    gbif_accepted_key: int | None = None,
    binomial_name: str | None = None,
) -> tuple[str, str]:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Ada", email, "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )

        image_id = uuid4()
        candidate_id = uuid4()
        await session.execute(
            insert(identification_images).values(
                id=image_id,
                user_id=user.id,
                storage_path=f"identifications/{image_id}.jpg",
                mime_type="image/jpeg",
                size_bytes=128,
                metadata={},
                status="needs_confirmation",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=image_id,
                common_name="Helecho",
                suggested_scientific_name="Nephrolepis exaltata",
                confidence_label="high",
                visible_traits=["fronds"],
                possible_match_copy="Matches a domestic fern.",
                accepted_scientific_name=accepted_scientific_name,
                gbif_accepted_key=gbif_accepted_key,
                binomial_name=binomial_name,
                validation_status=validation_status,
                confirmed_at=datetime.now(timezone.utc) if confirmed else None,
            )
        )
        await session.commit()

    return auth_session.token, str(candidate_id)


async def _create_profile(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    scientific_name: str,
    common_name: str | None = None,
    normalized_binomial: str | None = None,
    aliases: list | None = None,
    has_sections: bool = True,
) -> None:
    async with session_factory() as session:
        await session.execute(
            insert(plant_profiles).values(
                id=uuid4(),
                scientific_name=scientific_name,
                common_name=common_name,
                aliases=aliases or [],
                sections={"care": ["Some content."]} if has_sections else {},
                sources=[],
                confidence=0.5,
                limitations=[],
                normalized_binomial=normalized_binomial,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_search_local_profiles_matches_scientific_binomial_common_and_alias(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_profile(
        session_factory,
        scientific_name="Monstera deliciosa",
        common_name="Costilla de Adán",
        normalized_binomial="Monstera deliciosa",
        aliases=[{"name": "Hoja partida", "language": "es"}],
    )
    await _create_profile(
        session_factory,
        scientific_name="Solanum lycopersicum",
        common_name="Tomate",
        normalized_binomial="Solanum lycopersicum",
        aliases=[],
        has_sections=False,
    )

    async with session_factory() as session:
        from app.profile_garden.repository import PlantProfileGardenRepository

        repo = PlantProfileGardenRepository(session)

        scientific = await repo.search_local_profiles("Monstera")
        assert len(scientific) == 1
        assert scientific[0].matched_field == "scientific_name"
        assert scientific[0].scientific_name == "Monstera deliciosa"

        binomial = await repo.search_local_profiles("deliciosa")
        assert len(binomial) == 1
        assert binomial[0].scientific_name == "Monstera deliciosa"

        common = await repo.search_local_profiles("Tomate")
        assert len(common) == 1
        assert common[0].matched_field == "common_name"
        assert common[0].has_evidence is False

        alias = await repo.search_local_profiles("Hoja partida")
        assert len(alias) == 1
        assert alias[0].matched_field == "alias"
        assert alias[0].matched_value == "Hoja partida"


@pytest.mark.asyncio
async def test_search_local_profiles_returns_empty_for_no_match(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_profile(
        session_factory,
        scientific_name="Monstera deliciosa",
        common_name="Costilla de Adán",
    )

    async with session_factory() as session:
        from app.profile_garden.repository import PlantProfileGardenRepository

        repo = PlantProfileGardenRepository(session)
        results = await repo.search_local_profiles("zzz-no-such-plant")
        assert results == []
        assert await repo.search_local_profiles("   ") == []
