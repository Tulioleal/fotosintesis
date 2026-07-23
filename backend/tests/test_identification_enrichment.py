from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, insert, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    identification_candidates,
    identification_images,
    plant_profiles,
    taxonomy_provenance_snapshots,
)
from app.core.settings import get_settings
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import ENRICHMENT_POLICY_V1
from app.identification.confirmation import CandidateConfirmationService
from app.identification.repository import IdentificationRepository
from app.jobs.repository import JobRepository
from app.main import app


async def _candidate(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
) -> tuple[str, UUID, UUID]:
    async with session_factory() as session:
        auth = DatabaseAuthRepository(session)
        user = await auth.create_user("Owner", email, "password123")
        auth_session = await auth.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        identification_id = uuid4()
        candidate_id = uuid4()
        await session.execute(
            insert(identification_images).values(
                id=identification_id,
                user_id=user.id,
                storage_path=f"identifications/{identification_id}.jpg",
                mime_type="image/jpeg",
                size_bytes=128,
                metadata={},
                status="needs_confirmation",
                message="Confirm this plant.",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=identification_id,
                common_name="Swiss cheese plant",
                suggested_scientific_name="Monstera deliciosa",
                confidence_label="high",
                visible_traits=["fenestrated leaves"],
                possible_match_copy="Possible match.",
                gbif_key=2878688,
                gbif_accepted_key=2878688,
                accepted_scientific_name="Monstera deliciosa",
                binomial_name="Monstera deliciosa",
                taxonomic_status="ACCEPTED",
                synonyms=[],
                genus="Monstera",
                family="Araceae",
                species="Monstera deliciosa",
                validation_status="validated",
            )
        )
        await session.commit()
    return auth_session.token, identification_id, candidate_id


def _enable_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "true")
    get_settings.cache_clear()


async def test_confirmation_locks_identification_row_before_selecting_candidate() -> None:
    session = AsyncMock()
    session.execute.side_effect = [
        SimpleNamespace(first=lambda: SimpleNamespace(id=uuid4())),
        SimpleNamespace(first=lambda: None),
    ]

    await IdentificationRepository(session).confirm_candidate(
        identification_id=uuid4(),
        candidate_id=uuid4(),
        user_id=uuid4(),
    )

    statement = session.execute.await_args_list[0].args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql


async def test_binomial_only_taxonomy_predecessor_does_not_match_null_gbif_keys() -> None:
    session = AsyncMock()
    inserted_id = uuid4()
    session.scalar.side_effect = [None, None, inserted_id]

    result = await IdentificationRepository(session).create_or_reuse_taxonomy_snapshot(
        identity=CanonicalSpeciesIdentity(None, "Monstera deliciosa", True),
        source_version="v1",
        snapshot={},
        resolved_at=datetime.now(timezone.utc),
    )

    predecessor_statement = session.scalar.await_args_list[1].args[0]
    sql = str(predecessor_statement.compile(dialect=postgresql.dialect()))
    assert result == inserted_id
    assert "normalized_binomial" in sql
    assert "accepted_gbif_key IS NULL" not in sql


async def _confirm(client: AsyncClient, token: str, identification_id: UUID, candidate_id: UUID):
    return await client.post(
        f"/identifications/{identification_id}/candidates/{candidate_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_confirmation_requires_scheduling_and_rolls_back_on_failure(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, identification_id, candidate_id = await _candidate(
        session_factory, email="unavailable@example.com"
    )
    _enable_producer(monkeypatch)

    async def fail_scheduling(self, **kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(JobRepository, "associate_candidate_enrichment", fail_scheduling)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _confirm(client, token, identification_id, candidate_id)

    assert response.status_code == 503
    async with session_factory() as session:
        confirmed_at = await session.scalar(
            select(identification_candidates.c.confirmed_at).where(
                identification_candidates.c.id == candidate_id
            )
        )
        job_count = await session.scalar(select(func.count()).select_from(application_jobs))
        association_count = await session.scalar(
            select(func.count()).select_from(candidate_enrichment_jobs)
        )
        taxonomy_count = await session.scalar(
            select(func.count()).select_from(taxonomy_provenance_snapshots)
        )

    assert confirmed_at is None
    assert job_count == association_count == taxonomy_count == 0


@pytest.mark.asyncio
async def test_confirmation_is_unavailable_when_producer_is_disabled(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, identification_id, candidate_id = await _candidate(
        session_factory, email="producer-disabled@example.com"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _confirm(client, token, identification_id, candidate_id)

    assert response.status_code == 503
    async with session_factory() as session:
        assert await session.scalar(
            select(identification_candidates.c.confirmed_at).where(
                identification_candidates.c.id == candidate_id
            )
        ) is None
        assert await session.scalar(select(func.count()).select_from(application_jobs)) == 0


@pytest.mark.asyncio
async def test_confirmation_rejects_invalid_composite_identity_without_mutation(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, identification_id, candidate_id = await _candidate(
        session_factory, email="invalid-taxonomy@example.com"
    )
    _enable_producer(monkeypatch)
    async with session_factory() as session:
        await session.execute(
            update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(binomial_name=None)
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await _confirm(client, token, identification_id, candidate_id)

    assert response.status_code == 409
    async with session_factory() as session:
        assert await session.scalar(
            select(identification_candidates.c.confirmed_at).where(
                identification_candidates.c.id == candidate_id
            )
        ) is None
        assert await session.scalar(select(func.count()).select_from(application_jobs)) == 0


@pytest.mark.asyncio
async def test_successful_confirmation_uses_exactly_one_request_commit(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, identification_id, candidate_id = await _candidate(
        session_factory, email="single-commit@example.com"
    )
    _enable_producer(monkeypatch)
    async with session_factory() as session:
        user_id = await session.scalar(
            select(identification_images.c.user_id).where(
                identification_images.c.id == identification_id
            )
        )
        commits: list[None] = []
        event.listen(session.sync_session, "after_commit", lambda _: commits.append(None))

        response = await CandidateConfirmationService(session).confirm(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user_id,
        )

    assert response.enrichment.job.status.value == "pending"
    assert len(commits) == 1


@pytest.mark.asyncio
async def test_confirmation_replay_shares_active_work_and_status_is_owner_scoped(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    owner_token, owner_identification, owner_candidate = await _candidate(
        session_factory, email="first-owner@example.com"
    )
    other_token, other_identification, other_candidate = await _candidate(
        session_factory, email="second-owner@example.com"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await _confirm(client, owner_token, owner_identification, owner_candidate)
        replay = await _confirm(client, owner_token, owner_identification, owner_candidate)
        client.cookies.clear()
        shared = await _confirm(client, other_token, other_identification, other_candidate)
        client.cookies.clear()
        owner_status = await client.get(
            f"/identifications/candidates/{owner_candidate}/enrichment",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        client.cookies.clear()
        foreign_status = await client.get(
            f"/identifications/candidates/{owner_candidate}/enrichment",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        unknown_status = await client.get(
            f"/identifications/candidates/{uuid4()}/enrichment",
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert first.status_code == replay.status_code == shared.status_code == 200
    first_job = first.json()["enrichment"]["job"]
    assert replay.json()["enrichment"]["job"]["id"] == first_job["id"]
    assert shared.json()["enrichment"]["job"]["id"] == first_job["id"]
    assert first_job["status"] == "pending"
    assert "payload" not in first_job
    assert owner_status.status_code == 200
    assert foreign_status.status_code == unknown_status.status_code == 404
    assert foreign_status.json() == unknown_status.json()

    async with session_factory() as session:
        job_count = await session.scalar(select(func.count()).select_from(application_jobs))
        association_count = await session.scalar(
            select(func.count()).select_from(candidate_enrichment_jobs)
        )
        taxonomy_count = await session.scalar(
            select(func.count()).select_from(taxonomy_provenance_snapshots)
        )
    assert job_count == 1
    assert association_count == 2
    assert taxonomy_count == 1


@pytest.mark.asyncio
async def test_terminal_work_allows_a_new_eligible_candidate_run(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    first_token, first_identification, first_candidate = await _candidate(
        session_factory, email="terminal-first@example.com"
    )
    second_token, second_identification, second_candidate = await _candidate(
        session_factory, email="terminal-second@example.com"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await _confirm(client, first_token, first_identification, first_candidate)
        first_job_id = UUID(first.json()["enrichment"]["job"]["id"])
        async with session_factory() as session:
            await session.execute(
                update(application_jobs)
                .where(application_jobs.c.id == first_job_id)
                .values(
                    status="failed",
                    active_deduplication_key=None,
                    last_error={"category": "insufficient_evidence", "retryable": False},
                )
            )
            await session.commit()
        client.cookies.clear()
        second = await _confirm(client, second_token, second_identification, second_candidate)

    assert second.status_code == 200
    assert second.json()["enrichment"]["job"]["id"] != str(first_job_id)


@pytest.mark.asyncio
async def test_profile_keeps_snapshot_separate_from_every_enrichment_state(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_producer(monkeypatch)
    token, identification_id, candidate_id = await _candidate(
        session_factory, email="profile-enrichment@example.com"
    )
    snapshot_sections = {"care": ["Persisted snapshot care."]}
    snapshot_sources = [
        {
            "title": "Snapshot source",
            "url": "https://example.org/snapshot",
            "domain": "example.org",
            "confidence": 0.9,
        }
    ]
    async with session_factory() as session:
        await session.execute(
            insert(plant_profiles).values(
                id=uuid4(),
                scientific_name="Monstera deliciosa",
                common_name="Swiss cheese plant",
                aliases=[],
                sections=snapshot_sections,
                sources=snapshot_sources,
                confidence=0.9,
                limitations=["Snapshot limitation."],
            )
        )
        await session.commit()

    required_aspects = sorted(aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects)
    states = {
        "pending": {"result": None, "last_error": None},
        "processing": {"result": None, "last_error": None},
        "complete": {
            "result": {
                "outcome": "complete",
                "policy_version": 1,
                "covered_aspects": required_aspects,
                "missing_aspects": [],
                "covered_count": len(required_aspects),
                "missing_count": 0,
                "limitations": [],
                "acquisition_avoided": False,
            },
            "last_error": None,
        },
        "partial": {
            "result": {
                "outcome": "partial",
                "policy_version": 1,
                "covered_aspects": required_aspects[:1],
                "missing_aspects": required_aspects[1:],
                "covered_count": 1,
                "missing_count": len(required_aspects) - 1,
                "limitations": ["missing_required_aspects"],
                "acquisition_avoided": False,
            },
            "last_error": None,
        },
        "failed": {
            "result": None,
            "last_error": {"category": "insufficient_evidence", "retryable": False},
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        confirmation = await _confirm(client, token, identification_id, candidate_id)
        job_id = UUID(confirmation.json()["enrichment"]["job"]["id"])
        for lifecycle, metadata in states.items():
            async with session_factory() as session:
                await session.execute(
                    update(application_jobs)
                    .where(application_jobs.c.id == job_id)
                    .values(
                        status=lifecycle,
                        active_deduplication_key=(
                            None if lifecycle in {"complete", "partial", "failed"} else "active"
                        ),
                        result=metadata["result"],
                        last_error=metadata["last_error"],
                    )
                )
                await session.commit()
            response = await client.get(
                f"/plant-profiles/Monstera%20deliciosa?candidateId={candidate_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            body = response.json()
            assert response.status_code == 200
            assert body["sections"] == snapshot_sections
            assert body["sources"] == snapshot_sources
            assert body["limitations"] == ["Snapshot limitation."]
            assert body["enrichment"]["job"]["status"] == lifecycle
