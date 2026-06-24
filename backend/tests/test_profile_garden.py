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


async def _create_user_candidate(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    accepted_scientific_name: str | None,
    validation_status: str = "validated",
    confirmed: bool,
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
                validation_status=validation_status,
                confirmed_at=datetime.now(timezone.utc) if confirmed else None,
            )
        )
        await session.commit()

    return auth_session.token, str(candidate_id)
