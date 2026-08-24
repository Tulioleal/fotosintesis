"""HTTP-level tests for the owner-scoped enrichment activity endpoint."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.jobs.schemas import EnrichmentActivityResponse

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]

_SPECIES = {"accepted_gbif_key": 2878688, "normalized_binomial": "Monstera deliciosa"}


@pytest.fixture
async def http_client(pg_session_factory, test_user):
    """Build a fresh app per test so overrides never leak across tests."""
    from app.main import create_app
    from app.auth.dependencies import get_current_user
    from app.db.session import get_async_session

    class _FakeAuth:
        def __init__(self, uid: UUID) -> None:
            self.id = uid

    def _override_user():
        return _FakeAuth(test_user)

    async def _override_session():
        async with pg_session_factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_async_session] = _override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, test_user, pg_session_factory
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_async_session, None)


async def test_http_fixture_uses_its_postgres_schema(
    pg_session_factory,
    pg_schema,
):
    from sqlalchemy import text

    async with pg_session_factory() as session:
        actual = await session.scalar(text("select current_schema()"))

    assert actual == pg_schema


async def _seed_user(pg_session_factory, *, user_id: UUID, suffix: str) -> None:
    from app.auth.tables import users

    async with pg_session_factory() as session:
        await session.execute(
            users.insert().values(
                id=user_id,
                name="Owner",
                email=f"{user_id}@{suffix}",
                email_verified=True,
            )
        )
        await session.commit()


async def _seed_enrichment(
    pg_session_factory,
    *,
    user_id: UUID,
    status: str = "pending",
    scientific_name: str = "Monstera deliciosa",
    completed_at: datetime | None = None,
    result: dict | None = None,
    last_error: dict | None = None,
    species: dict | None = None,
    updated_at: datetime | None = None,
) -> tuple[UUID, UUID]:
    from app.auth.tables import (
        application_jobs,
        candidate_enrichment_jobs,
        enrichment_telemetry_observations,
        identification_candidates,
        identification_images,
    )

    job_id = uuid4()
    identification_id = uuid4()
    candidate_id = uuid4()
    now = updated_at or datetime.now(UTC)
    if completed_at is not None:
        now = min(now, completed_at)
    async with pg_session_factory() as session:
        await session.execute(
            identification_images.insert().values(
                id=identification_id,
                user_id=user_id,
                storage_path="plant.jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                metadata={},
                status="needs_confirmation",
            )
        )
        await session.execute(
            identification_candidates.insert().values(
                id=candidate_id,
                identification_id=identification_id,
                user_id=user_id,
                suggested_scientific_name=scientific_name,
                accepted_scientific_name=scientific_name,
                binomial_name=scientific_name,
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Possible match.",
                taxonomic_status="ACCEPTED",
                synonyms=[],
                validation_status="validated",
            )
        )
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                user_id=user_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={
                    "run_id": str(job_id),
                    "policy_version": 1,
                    "species": species or _SPECIES,
                    "secret_payload_marker": "should-not-leak",
                },
                status=status,
                idempotency_key=f"enrich-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=now,
                updated_at=now,
                completed_at=completed_at,
                result=result,
                last_error=last_error,
            )
        )
        await session.execute(
            candidate_enrichment_jobs.insert().values(
                id=uuid4(),
                user_id=user_id,
                candidate_id=candidate_id,
                job_id=job_id,
                policy_version=1,
            )
        )
        if status in ("complete", "partial", "failed"):
            await session.execute(
                enrichment_telemetry_observations.insert().values(
                    job_id=job_id,
                    policy_label="1",
                    lifecycle_outcome=status,
                    acquisition_avoided=False,
                    local_covered_count=1,
                    final_covered_count=1,
                    coverage_gain=1,
                    accepted_aspect_count=1,
                    search_count=1,
                    duration_seconds=1.0,
                )
            )
        await session.commit()
    return job_id, candidate_id


async def _seed_refresh(
    pg_session_factory,
    *,
    species: dict,
    status: str = "pending",
    completed_at: datetime | None = None,
    result: dict | None = None,
    enrichment_job_ids: list[UUID] | None = None,
) -> UUID:
    from app.auth.tables import (
        application_jobs,
        profile_refresh_enrichment_jobs,
    )

    job_id = uuid4()
    now = datetime.now(UTC)
    if completed_at is not None:
        now = min(now, completed_at)
    async with pg_session_factory() as session:
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                user_id=None,
                job_type="refresh_profile",
                payload_version=1,
                payload={
                    "policy_version": 1,
                    "species": species,
                    "fingerprint": "fp",
                    "run_id": str(job_id),
                    "secret_payload_marker": "should-not-leak",
                },
                status=status,
                idempotency_key=f"refresh-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=now,
                updated_at=now,
                completed_at=completed_at,
                result=result,
            )
        )
        for enrichment_job_id in enrichment_job_ids or []:
            await session.execute(
                profile_refresh_enrichment_jobs.insert().values(
                    refresh_job_id=job_id,
                    enrichment_job_id=enrichment_job_id,
                )
            )
        await session.commit()
    return job_id


async def test_owner_reads_active_and_terminal_activity(http_client):
    client, user, factory = http_client
    active_id, candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    terminal_id, terminal_candidate_id = await _seed_enrichment(
        factory,
        user_id=user,
        status="complete",
        completed_at=datetime.now(UTC) - timedelta(hours=1),
        result={
            "outcome": "complete",
            "policy_version": 1,
            "covered_aspects": ["light_exposure"],
            "missing_aspects": [],
            "covered_count": 1,
            "missing_count": 0,
            "limitations": [],
            "acquisition_avoided": False,
        },
    )
    refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[terminal_id],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200, response.text
    # Owner-scoped data must never be cacheable by any intermediary.
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Pragma"] == "no-cache"
    body = EnrichmentActivityResponse.model_validate(response.json())
    by_id = {item.id: item for item in body.items}
    assert set(by_id) == {active_id, terminal_id, refresh_id}
    assert body.has_more is False

    active = by_id[active_id]
    assert active.status.value == "processing"
    assert active.candidate_id == candidate_id
    assert active.scientific_name == "Monstera deliciosa"
    assert active.phase.value == "evidence"
    assert active.completed_at is None

    terminal = by_id[terminal_id]
    assert terminal.status.value == "complete"
    assert terminal.result is not None
    assert terminal.result.outcome == "complete"
    assert terminal.result.covered_count == 1

    refresh = by_id[refresh_id]
    assert refresh.phase.value == "profile_refresh"
    assert refresh.job_type.value == "refresh_profile"
    # The refresh surfaces the authorized owner-candidate context of the
    # enrichment run that caused it.
    assert refresh.candidate_id == terminal_candidate_id
    assert refresh.scientific_name == "Monstera deliciosa"
    assert refresh.status.value == "processing"

    # Raw payload and ownership internals must never leak.
    for forbidden in (
        "secret_payload_marker",
        "fingerprint",
        "payload",
        "lease_token",
        "lease_owner",
        "idempotency_key",
    ):
        assert forbidden not in response.text, f"leaked {forbidden!r}"


async def test_activity_is_owner_scoped(http_client, pg_engine):
    from app.auth.tables import users
    from sqlalchemy.ext.asyncio import AsyncSession

    client, user, factory = http_client
    foreign_owner_id = uuid4()
    async with AsyncSession(pg_engine) as s:
        await s.execute(
            users.insert().values(
                id=foreign_owner_id,
                name="Foreign",
                email=f"{foreign_owner_id}@foreign.invalid",
                email_verified=True,
            )
        )
        await s.commit()

    owned_job_id, _ = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    owned_refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[owned_job_id],
    )
    foreign_job_id, foreign_candidate_id = await _seed_enrichment(
        factory, user_id=foreign_owner_id, status="processing"
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["items"]} == {
        str(owned_job_id),
        str(owned_refresh_id),
    }
    assert body["has_more"] is False
    assert str(foreign_job_id) not in response.text
    assert str(foreign_candidate_id) not in response.text
    assert str(foreign_owner_id) not in response.text


async def test_terminal_outside_retention_is_excluded(http_client):
    client, user, factory = http_client
    await _seed_enrichment(
        factory,
        user_id=user,
        status="failed",
        completed_at=datetime.now(UTC) - timedelta(days=7),
        last_error={"category": "attempts_exhausted", "retryable": False},
    )
    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_failed_job_returns_sanitized_error_category(http_client):
    client, user, factory = http_client
    job_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="failed",
        completed_at=datetime.now(UTC) - timedelta(minutes=5),
        last_error={"category": "provider_transient", "retryable": True},
    )
    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    body = response.json()
    item = next(item for item in body["items"] if item["id"] == str(job_id))
    assert item["result"] is None
    assert item["last_error"] == {
        "category": "provider_transient",
        "retryable": True,
    }


async def test_bounded_cap_via_limit_query(http_client):
    client, user, factory = http_client
    for index in range(5):
        await _seed_enrichment(
            factory,
            user_id=user,
            status="pending",
            scientific_name=f"Species {index}",
        )
    response = await client.get("/jobs/enrichment-activity?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["has_more"] is True


async def test_unauthenticated_returns_401(pg_session_factory):
    from app.main import create_app
    from app.auth.dependencies import get_current_user
    from app.db.session import get_async_session

    def _unauth():
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    async def _override_session():
        async with pg_session_factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_current_user] = _unauth
    app.dependency_overrides[get_async_session] = _override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/jobs/enrichment-activity")
            assert response.status_code == 401
            # Error statuses carry the same private-cache headers as 200s.
            assert response.headers["Cache-Control"] == "private, no-store"
            assert response.headers["Pragma"] == "no-cache"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_async_session, None)


async def test_response_shape_is_stable_and_bounded(http_client):
    client, user, factory = http_client
    await _seed_enrichment(factory, user_id=user, status="pending")
    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    body = response.json()
    # Every item carries exactly the sanitized metadata keys.
    allowed_keys = {
        "id",
        "job_type",
        "phase",
        "status",
        "created_at",
        "updated_at",
        "completed_at",
        "species_key",
        "scientific_name",
        "common_name",
        "candidate_id",
        "result",
        "last_error",
    }
    for item in body["items"]:
        assert set(item.keys()) == allowed_keys, item.keys()
    for forbidden in (
        "payload",
        "claims",
        "quote",
        "evidence_quote",
        "source_body",
        "lease_owner",
        "lease_token",
        "idempotency_key",
        "user_id",
    ):
        assert forbidden not in json.dumps(body), f"leaked {forbidden!r}"

async def test_pagination_walk_covers_every_job_exactly_once(http_client):
    client, user, factory = http_client
    expected: set[str] = set()
    base = datetime.now(UTC) - timedelta(minutes=30)
    anchor_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="processing",
        updated_at=base,
    )
    expected.add(str(anchor_id))
    for index in range(1, 3):
        job_id, _ = await _seed_enrichment(
            factory,
            user_id=user,
            status="processing",
            updated_at=base + timedelta(minutes=index),
        )
        expected.add(str(job_id))
    for index in range(2):
        refresh_id = await _seed_refresh(
            factory,
            species=_SPECIES,
            status="processing",
            enrichment_job_ids=[anchor_id],
        )
        # Refresh timestamps need control; re-touch via direct update.
        from app.auth.tables import application_jobs
        from sqlalchemy import update as sa_update

        async with factory() as session:
            await session.execute(
                sa_update(application_jobs)
                .where(application_jobs.c.id == refresh_id)
                .values(
                    created_at=base,
                    updated_at=base + timedelta(minutes=3 + index),
                )
            )
            await session.commit()
        expected.add(str(refresh_id))
    assert len(expected) == 5

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = await client.get("/jobs/enrichment-activity", params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        seen.extend(item["id"] for item in body["items"])
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body["next_cursor"]
        assert cursor

    assert len(seen) == len(set(seen)), "pagination must not duplicate jobs"
    assert set(seen) == expected, "pagination must not omit jobs"


async def test_malformed_cursor_returns_422(http_client):
    import base64 as b64

    client, _, _ = http_client
    cases = [
        "not-valid-base64!!!",
        b64.urlsafe_b64encode(b"not json at all").decode().rstrip("="),
        b64.urlsafe_b64encode(b'{"missing": "fields"}').decode().rstrip("="),
        b64.urlsafe_b64encode(
            b'{"updated_at": "nope", "id": "also-nope"}'
        ).decode().rstrip("="),
    ]
    for raw_cursor in cases:
        response = await client.get(
            "/jobs/enrichment-activity",
            params={"cursor": raw_cursor},
        )
        assert response.status_code == 422, (raw_cursor, response.text)
        assert response.headers["Cache-Control"] == "private, no-store"


async def test_equal_timestamps_order_by_exact_id_descending(http_client):
    client, user, factory = http_client
    stamp = datetime.now(UTC) - timedelta(minutes=5)
    seeded = []
    for index in range(3):
        job_id, _ = await _seed_enrichment(
            factory,
            user_id=user,
            status="pending",
            updated_at=stamp,
        )
        seeded.append(job_id)

    first = await client.get("/jobs/enrichment-activity", params={"limit": 10})
    second = await client.get("/jobs/enrichment-activity", params={"limit": 10})
    ids_first = [item["id"] for item in first.json()["items"]]
    ids_second = [item["id"] for item in second.json()["items"]]
    assert ids_first == ids_second, "ordering must be stable across requests"
    assert ids_first == [
        str(job_id)
        for job_id in sorted(seeded, key=lambda j: str(j), reverse=True)
    ]


async def test_configured_max_items_override_limit_100(http_client, monkeypatch):
    client, user, factory = http_client
    monkeypatch.setenv("ENRICHMENT_ACTIVITY_MAX_ITEMS", "2")
    from app.core.settings import get_settings

    get_settings.cache_clear()
    try:
        for index in range(4):
            await _seed_enrichment(
                factory,
                user_id=user,
                status="pending",
                scientific_name=f"Species {index}",
            )
        response = await client.get("/jobs/enrichment-activity?limit=100")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["has_more"] is True
    finally:
        get_settings.cache_clear()


async def test_foreign_candidate_context_never_leaks(http_client):
    from sqlalchemy.ext.asyncio import AsyncSession

    client, user, factory = http_client
    foreign_owner = uuid4()
    await _seed_user(factory, user_id=foreign_owner, suffix="foreign-leak.invalid")
    foreign_job_id, foreign_candidate_id = await _seed_enrichment(
        factory, user_id=foreign_owner, status="processing"
    )
    owned_job_id, owned_candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert ids == {str(owned_job_id)}
    candidate_ids = {
        item["candidate_id"] for item in body["items"] if item["candidate_id"]
    }
    assert candidate_ids == {str(owned_candidate_id)}
    assert str(foreign_job_id) not in response.text
    assert str(foreign_candidate_id) not in response.text


async def test_malformed_association_cannot_bypass_ownership(
    http_client, pg_session_factory
):
    """An association row pointing a refresh at another user's enrichment
    must not surface that refresh to anyone who does not own an authorized
    candidate or image behind the chain."""
    from sqlalchemy.ext.asyncio import AsyncSession

    client, user, factory = http_client
    foreign_owner = uuid4()
    await _seed_user(factory, user_id=foreign_owner, suffix="foreign-assoc.invalid")
    foreign_enrichment_id, _ = await _seed_enrichment(
        factory, user_id=foreign_owner, status="complete"
    )
    refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[foreign_enrichment_id],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert str(refresh_id) not in response.text


async def test_shared_refresh_appears_once_per_owner(http_client):
    client, user, factory = http_client
    enrich_a, _ = await _seed_enrichment(factory, user_id=user, status="processing")
    enrich_b, _ = await _seed_enrichment(
        factory, user_id=user, status="complete", completed_at=datetime.now(UTC)
    )
    shared_refresh = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[enrich_a, enrich_b],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.count(str(shared_refresh)) == 1


async def test_refresh_uses_accepted_scientific_name(http_client, pg_session_factory):
    from app.auth.tables import identification_candidates
    from sqlalchemy import update as sa_update

    client, user, factory = http_client
    enrich_id, candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    async with pg_session_factory() as session:
        await session.execute(
            sa_update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(accepted_scientific_name="Monstera adansonii")
        )
        await session.commit()

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {
        item["id"]: item for item in response.json()["items"]
    }
    # The accepted scientific name wins over the payload's normalized
    # binomial when the two differ.
    assert items[str(enrich_id)]["scientific_name"] == "Monstera adansonii"


async def test_oversized_persisted_results_are_bounded(http_client):
    client, user, factory = http_client
    huge_limitations = [{"bogus": True}] * 500
    await _seed_enrichment(
        factory,
        user_id=user,
        status="partial",
        completed_at=datetime.now(UTC),
        result={
            "outcome": "partial",
            "policy_version": 1,
            "covered_aspects": ["light_exposure"],
            "missing_aspects": [],
            "covered_count": 10**6,
            "missing_count": -5,
            "limitations": ["not-a-limitation", "also-bogus"],
            "acquisition_avoided": False,
            **{"extra_noise": huge_limitations},
        },
    )
    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    item = response.json()["items"][0]
    result = item["result"]
    assert result["covered_count"] <= 32
    assert result["missing_count"] >= 0
    assert result["limitations"] == []


async def test_outcome_variants_are_serialized(http_client):
    client, user, factory = http_client
    complete_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="complete",
        completed_at=datetime.now(UTC),
        result={
            "outcome": "complete",
            "policy_version": 1,
            "covered_aspects": ["light_exposure"],
            "missing_aspects": [],
            "covered_count": 1,
            "missing_count": 0,
            "limitations": [],
            "acquisition_avoided": False,
        },
    )
    partial_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="partial",
        completed_at=datetime.now(UTC),
        result={
            "outcome": "partial",
            "policy_version": 1,
            "covered_aspects": ["light_exposure"],
            "missing_aspects": ["watering"],
            "covered_count": 1,
            "missing_count": 1,
            "limitations": ["missing_required_aspects"],
            "acquisition_avoided": False,
        },
    )
    failed_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="failed",
        completed_at=datetime.now(UTC),
        last_error={"category": "provider_transient", "retryable": True},
    )
    noop_refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="complete",
        completed_at=datetime.now(UTC),
        result={
            "outcome": "noop",
            "policy_version": 1,
            "regenerated_sections": [],
            "stale_sections": [],
            "limitations": [],
        },
        enrichment_job_ids=[complete_id],
    )

    response = await client.get("/jobs/enrichment-activity", params={"limit": 10})
    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert set(by_id) == {
        str(complete_id),
        str(partial_id),
        str(failed_id),
        str(noop_refresh_id),
    }
    assert by_id[str(complete_id)]["result"]["outcome"] == "complete"
    assert by_id[str(partial_id)]["result"]["outcome"] == "partial"
    assert by_id[str(partial_id)]["result"]["limitations"] == [
        "missing_required_aspects"
    ]
    assert by_id[str(failed_id)]["last_error"]["category"] == "provider_transient"
    assert by_id[str(noop_refresh_id)]["result"]["outcome"] == "noop"


async def _seed_generic_job(
    pg_session_factory,
    *,
    job_type: str,
    status: str = "complete",
) -> UUID:
    from app.auth.tables import application_jobs

    job_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                user_id=None,
                job_type=job_type,
                payload_version=1,
                payload={"run_id": str(job_id)},
                status=status,
                idempotency_key=f"{job_type}-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
            )
        )
        await session.commit()
    return job_id


async def _associate(
    pg_session_factory,
    *,
    refresh_job_id: UUID,
    enrichment_job_id: UUID,
) -> None:
    from app.auth.tables import profile_refresh_enrichment_jobs

    async with pg_session_factory() as session:
        await session.execute(
            profile_refresh_enrichment_jobs.insert().values(
                refresh_job_id=refresh_job_id,
                enrichment_job_id=enrichment_job_id,
            )
        )
        await session.commit()


async def test_refresh_with_foreign_association_owner_is_hidden(http_client):
    """The requester owns the candidate, but the candidate-enrichment
    association on the causing job belongs to another user."""
    client, user, factory = http_client
    foreign_owner = uuid4()
    await _seed_user(factory, user_id=foreign_owner, suffix="assoc-owner.invalid")

    # Foreign enrichment run associated (via cej.user_id) with a foreign user.
    foreign_enrichment_id, foreign_candidate_id = await _seed_enrichment(
        factory, user_id=foreign_owner, status="processing"
    )
    refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[foreign_enrichment_id],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(refresh_id) not in ids
    assert str(foreign_candidate_id) not in response.text


async def test_association_to_non_enrichment_causing_job_is_hidden(http_client):
    client, user, factory = http_client
    owned_enrichment_id, owned_candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    ingest_job_id = await _seed_generic_job(
        factory, job_type="ingest_validated_claims"
    )
    # The refresh's ONLY causal link points at a non-enrichment job, so no
    # valid causing-enrichment authorization exists.
    refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
    )
    await _associate(
        factory,
        refresh_job_id=refresh_id,
        enrichment_job_id=ingest_job_id,
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert str(refresh_id) not in items
    assert str(ingest_job_id) not in response.text


async def test_reversed_or_unrelated_association_is_rejected(
    pg_session_factory,
):
    """Repository-level guard: reversed or unrelated job roles cannot be
    associated."""
    from app.jobs.repository import JobRepository

    refresh_id = await _seed_refresh(pg_session_factory, species=_SPECIES)
    some_owner = uuid4()
    await _seed_user(pg_session_factory, user_id=some_owner, suffix="roles.invalid")
    enrichment_a, _ = await _seed_enrichment(
        pg_session_factory, user_id=some_owner, status="processing"
    )
    ingest_id = await _seed_generic_job(
        pg_session_factory, job_type="ingest_validated_claims"
    )

    async with pg_session_factory() as session:
        repo = JobRepository(session)

        # Reversed roles: the "refresh" slot holds an enrichment job.
        with pytest.raises(ValueError, match="not a profile refresh job"):
            await repo.associate_profile_refresh(
                refresh_job_id=enrichment_a,
                enrichment_job_id=refresh_id,
            )

        # Unrelated role: the "enrichment" slot holds an ingestion job.
        with pytest.raises(ValueError, match="not an enrichment job"):
            await repo.associate_profile_refresh(
                refresh_job_id=refresh_id,
                enrichment_job_id=ingest_id,
            )


async def test_ownership_revocation_after_association_hides_refresh(
    http_client,
    pg_session_factory,
):
    from app.auth.tables import identification_images
    from sqlalchemy import update as sa_update
    from sqlalchemy.ext.asyncio import AsyncSession

    client, user, factory = http_client
    owned_job_id, owned_candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    refresh_id = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[owned_job_id],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert str(refresh_id) in {
        item["id"] for item in response.json()["items"]
    }

    # Transfer ownership away: both candidate and image now belong to someone
    # else, so neither ownership branch matches anymore.
    new_owner = uuid4()
    await _seed_user(factory, user_id=new_owner, suffix="new-owner.invalid")
    from app.auth.tables import identification_candidates

    async with pg_session_factory() as session:
        await session.execute(
            sa_update(identification_images)
            .where(
                identification_images.c.id.in_(
                    select(identification_candidates.c.identification_id).where(
                        identification_candidates.c.id == owned_candidate_id
                    )
                )
            )
            .values(user_id=new_owner)
        )
        await session.execute(
            sa_update(identification_candidates)
            .where(identification_candidates.c.id == owned_candidate_id)
            .values(user_id=new_owner)
        )
        await session.commit()

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(refresh_id) not in ids
    assert str(owned_job_id) not in ids


async def test_candidate_status_and_activity_agree_on_visibility(
    http_client, pg_session_factory
):
    """Direct candidate-status lookup and the activity endpoint must agree:
    what one hides, the other hides."""
    from app.jobs.repository import JobRepository

    client, user, factory = http_client
    foreign_owner = uuid4()
    await _seed_user(factory, user_id=foreign_owner, suffix="agree.invalid")
    foreign_job_id, foreign_candidate_id = await _seed_enrichment(
        factory, user_id=foreign_owner, status="processing"
    )

    async with pg_session_factory() as session:
        direct = await JobRepository(session).get_candidate_enrichment_status(
            candidate_id=foreign_candidate_id,
            user_id=user,
            policy_version=1,
        )
    assert direct is None

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(foreign_job_id) not in ids


async def test_every_item_requires_candidate_context(http_client):
    client, user, factory = http_client
    enrich_id, _ = await _seed_enrichment(factory, user_id=user, status="processing")
    await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[enrich_id],
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["phase"] for item in items} == {"evidence", "profile_refresh"}
    for item in items:
        assert item["candidate_id"], item
        assert item["scientific_name"], item


async def test_accepted_scientific_name_precedence(http_client, pg_session_factory):
    from app.auth.tables import identification_candidates
    from sqlalchemy import update as sa_update

    client, user, factory = http_client
    enrich_id, candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing"
    )
    # Suggested differs from accepted: accepted must win.
    async with pg_session_factory() as session:
        await session.execute(
            sa_update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(
                suggested_scientific_name="Suggested fallback name",
                binomial_name="Payload style binomial",
            )
        )
        await session.commit()

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[str(enrich_id)]["scientific_name"] == "Monstera deliciosa"
    assert items[str(enrich_id)]["scientific_name"] != "Suggested fallback name"

    # With no accepted name at all, suggested becomes the display name.
    async with pg_session_factory() as session:
        await session.execute(
            sa_update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(
                accepted_scientific_name=None,
                suggested_scientific_name="Monstera deliciosa",
            )
        )
        await session.commit()

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[str(enrich_id)]["scientific_name"] == "Monstera deliciosa"


async def test_malformed_candidate_rows_are_excluded(http_client, pg_session_factory):
    """A visible job whose candidate lacks any display name is filtered out in
    SQL instead of being returned without a usable profile link."""
    from app.auth.tables import identification_candidates
    from sqlalchemy import update as sa_update

    client, user, factory = http_client
    good_id, _ = await _seed_enrichment(
        factory, user_id=user, status="processing", scientific_name="Good plant"
    )
    bad_id, bad_candidate_id = await _seed_enrichment(
        factory, user_id=user, status="processing", scientific_name="Bad plant"
    )
    async with pg_session_factory() as session:
        await session.execute(
            sa_update(identification_candidates)
            .where(identification_candidates.c.id == bad_candidate_id)
            .values(
                accepted_scientific_name=None,
                # NOT NULL column: a blank name is the reachable malformed case.
                suggested_scientific_name="   ",
            )
        )
        await session.commit()

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(bad_id) not in ids
    assert str(good_id) in ids


@pytest.mark.parametrize(
    "result_payload",
    [
        "invalid",
        [],
        {"limitations": [{"unexpected": True}, []]},
        {"outcome": "unknown"},
    ],
)
async def test_corrupt_result_shapes_return_sanitized_items(
    http_client, result_payload
):
    client, user, factory = http_client
    job_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="partial",
        completed_at=datetime.now(UTC),
        result=result_payload,
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    item = items[str(job_id)]
    if item["result"] is not None:
        assert item["result"]["outcome"] in (None, "complete", "partial", "noop")
        for limitation in item["result"]["limitations"]:
            assert limitation in {
                "missing_required_aspects",
                "safety_evidence_rejected",
                "retry_exhausted",
                "workflow_incomplete",
                "indexing_deferred",
            }
    assert "invalid" not in json.dumps(item)


async def test_internal_error_categories_are_dropped(http_client):
    client, user, factory = http_client
    job_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="failed",
        completed_at=datetime.now(UTC),
        last_error={"category": "internal-provider-message"},
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[str(job_id)]["last_error"] is None
    assert "internal-provider-message" not in response.text


async def test_oversized_counts_and_limitations_are_clamped(http_client):
    client, user, factory = http_client
    job_id, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="partial",
        completed_at=datetime.now(UTC),
        result={
            "outcome": "partial",
            "covered_count": 10**9,
            "missing_count": -(10**9),
            "limitations": ["missing_required_aspects"] * 500,
        },
    )

    response = await client.get("/jobs/enrichment-activity")
    assert response.status_code == 200
    result = next(
        item["result"]
        for item in response.json()["items"]
        if item["id"] == str(job_id)
    )
    assert 0 <= result["covered_count"] <= 32
    assert 0 <= result["missing_count"] <= 32
    assert len(result["limitations"]) <= 10


async def test_cursor_validation_rejects_every_malformed_shape(http_client):
    import base64 as b64

    client, _, _ = http_client

    def b64url(payload: bytes) -> str:
        return b64.urlsafe_b64encode(payload).decode().rstrip("=")

    now_iso = "2026-08-13T00:00:00+00:00"
    valid_id = "00000000-0000-4000-8000-000000000010"
    malformed = [
        # Blank / whitespace.
        "",
        "   ",
        # Invalid base64.
        "not-valid-base64!!!",
        # Valid base64, invalid JSON.
        b64url(b"not json at all"),
        # Extra fields.
        b64url(
            json.dumps(
                {
                    "updated_at": now_iso,
                    "id": valid_id,
                    "extra": True,
                }
            ).encode()
        ),
        # Missing fields.
        b64url(json.dumps({"updated_at": now_iso}).encode()),
        b64url(json.dumps({"id": valid_id}).encode()),
        # Date-only timestamp.
        b64url(
            json.dumps({"updated_at": "2026-08-13", "id": valid_id}).encode()
        ),
        # Timezone-less timestamp.
        b64url(
            json.dumps(
                {"updated_at": "2026-08-13T00:00:00", "id": valid_id}
            ).encode()
        ),
        # Invalid UUID.
        b64url(
            json.dumps({"updated_at": now_iso, "id": "nope"}).encode()
        ),
    ]
    # Noncanonical/mixed alphabet: these bytes encode with urlsafe-only
    # characters (-_); swapping them to +/ yields different bytes that cannot
    # decode to the expected two-field payload.
    probe = b64.urlsafe_b64encode(b"\xfb\xff\xbf").decode().rstrip("=")
    assert "-" in probe or "_" in probe
    malformed.append(probe.replace("-", "+").replace("_", "/"))
    for raw_cursor in malformed:
        response = await client.get(
            "/jobs/enrichment-activity",
            params={"cursor": raw_cursor},
        )
        assert response.status_code == 422, (raw_cursor, response.text)


async def test_overlong_cursor_returns_422(http_client):
    client, _, _ = http_client
    response = await client.get(
        "/jobs/enrichment-activity",
        params={"cursor": "A" * 513},
    )
    assert response.status_code == 422


async def test_timezone_offset_is_normalized(http_client):
    """A cursor with a non-UTC offset still orders correctly."""
    import base64 as b64

    client, user, factory = http_client
    first, _ = await _seed_enrichment(factory, user_id=user, status="processing")
    second, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="processing",
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    page1 = await client.get(
        "/jobs/enrichment-activity", params={"limit": 1}
    )
    body = page1.json()
    assert [item["id"] for item in body["items"]] == [str(first)]
    assert body["next_cursor"]

    payload = json.loads(
        b64.urlsafe_b64decode(body["next_cursor"] + "=" * (-len(body["next_cursor"]) % 4))
    )
    # Rewrite the timestamp with a fixed +02:00 offset (not host-local) so the
    # normalization is proven without depending on the runner's timezone.
    from datetime import datetime as dt

    parsed = dt.fromisoformat(payload["updated_at"]).astimezone(
        timezone(timedelta(hours=2))
    )
    payload["updated_at"] = parsed.isoformat()
    recoded = b64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    page2 = await client.get(
        "/jobs/enrichment-activity", params={"limit": 10, "cursor": recoded}
    )
    assert page2.status_code == 200, page2.text
    assert {item["id"] for item in page2.json()["items"]} == {str(second)}


async def test_tied_association_timestamps_pick_deterministic_candidate(
    http_client,
    pg_session_factory,
):
    """Two candidates tied on association created_at resolve by candidate id
    descending — identically across repeated requests."""
    from app.auth.tables import (
        application_jobs,
        candidate_enrichment_jobs,
        identification_candidates,
        identification_images,
    )
    from sqlalchemy import select, update as sa_update

    client, user, factory = http_client
    job_id = uuid4()
    stamp = datetime.now(UTC)
    candidates = []
    async with factory() as session:
        for index in range(2):
            image_id = uuid4()
            candidate_id = uuid4()
            await session.execute(
                identification_images.insert().values(
                    id=image_id,
                    user_id=user,
                    storage_path=f"p{index}.jpg",
                    mime_type="image/jpeg",
                    size_bytes=10,
                    metadata={},
                    status="needs_confirmation",
                )
            )
            await session.execute(
                identification_candidates.insert().values(
                    id=candidate_id,
                    identification_id=image_id,
                    user_id=user,
                    suggested_scientific_name="Monstera deliciosa",
                    accepted_scientific_name=(
                        f"Monstera deliciosa {index}"
                        if index == 0
                        else "Monstera deliciosa 1"
                    ),
                    binomial_name="Monstera deliciosa",
                    confidence_label="high",
                    visible_traits=[],
                    possible_match_copy="Possible match.",
                    taxonomic_status="ACCEPTED",
                    synonyms=[],
                    validation_status="validated",
                )
            )
            candidates.append(candidate_id)
        await session.execute(
            application_jobs.insert().values(
                id=job_id,
                user_id=user,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={
                    "run_id": str(job_id),
                    "species": _SPECIES,
                },
                status="processing",
                idempotency_key=f"tie-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        # Tied created_at on both associations.
        await session.execute(
            candidate_enrichment_jobs.insert().values(
                id=uuid4(),
                user_id=user,
                candidate_id=candidates[0],
                job_id=job_id,
                policy_version=1,
                created_at=stamp,
            )
        )
        await session.execute(
            candidate_enrichment_jobs.insert().values(
                id=uuid4(),
                user_id=user,
                candidate_id=candidates[1],
                job_id=job_id,
                policy_version=1,
                created_at=stamp,
            )
        )
        await session.commit()

    expected_candidate = max(candidates)  # id-descending tie-break

    responses = [
        await client.get("/jobs/enrichment-activity"),
        await client.get("/jobs/enrichment-activity"),
    ]
    for response in responses:
        assert response.status_code == 200
        items = {
            item["id"]: item for item in response.json()["items"]
        }
        assert items[str(job_id)]["candidate_id"] == str(expected_candidate)


async def test_pagination_boundary_with_tied_evidence_and_refresh(
    http_client,
):
    """Evidence and refresh jobs sharing an exact updated_at are split across
    pages without duplication or omission."""
    client, user, factory = http_client
    anchor_id, _ = await _seed_enrichment(factory, user_id=user, status="processing")
    tie_stamp = datetime.now(UTC)

    enrich_tied, _ = await _seed_enrichment(
        factory,
        user_id=user,
        status="processing",
        updated_at=tie_stamp,
    )
    refresh_tied = await _seed_refresh(
        factory,
        species=_SPECIES,
        status="processing",
        enrichment_job_ids=[anchor_id],
    )

    from app.auth.tables import application_jobs
    from sqlalchemy import update as sa_update

    async with factory() as session:
        await session.execute(
            sa_update(application_jobs)
            .where(application_jobs.c.id == refresh_tied)
            .values(updated_at=tie_stamp, created_at=tie_stamp)
        )
        await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = await client.get("/jobs/enrichment-activity", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.extend(item["id"] for item in body["items"])
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body["next_cursor"]

    assert sorted(seen) == sorted({str(anchor_id), str(enrich_tied), str(refresh_tied)})
    assert len(seen) == len(set(seen))
