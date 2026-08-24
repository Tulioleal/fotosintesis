"""Owner-scoped enrichment activity repository tests.

These run against the in-memory SQLite metadata mirror so the retention,
ownership, phase, and sanitization boundaries are exercised without a live
PostgreSQL server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import insert, select

from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    identification_candidates,
    identification_images,
    profile_refresh_enrichment_jobs,
    users,
)
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    EnrichmentActivityPhase,
    JobFailureCategory,
    JobType,
)

RETENTION = timedelta(hours=24)
_SPECIES = {"accepted_gbif_key": 2878688, "normalized_binomial": "Monstera deliciosa"}
_OTHER_SPECIES = {"accepted_gbif_key": 99999, "normalized_binomial": "Ficus elastica"}


def _now() -> datetime:
    return datetime.now(UTC)


async def _seed_user(session_factory, *, user_id: UUID, suffix: str) -> None:
    async with session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                name="Owner",
                email=f"{user_id}@{suffix}",
            )
        )
        await session.commit()


async def _seed_enrichment(
    session_factory,
    *,
    user_id: UUID,
    status: str = "pending",
    species: dict | None = None,
    scientific_name: str = "Monstera deliciosa",
    common_name: str | None = None,
    completed_at: datetime | None = None,
    result: dict | None = None,
    last_error: dict | None = None,
    updated_at: datetime | None = None,
) -> tuple[UUID, UUID]:
    job_id = uuid4()
    identification_id = uuid4()
    candidate_id = uuid4()
    now = updated_at or _now()
    if completed_at is not None:
        now = min(now, completed_at)
    async with session_factory() as session:
        await session.execute(
            insert(identification_images).values(
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
            insert(identification_candidates).values(
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
                common_name=common_name,
            )
        )
        await session.execute(
            insert(application_jobs).values(
                id=job_id,
                user_id=user_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={
                    "run_id": str(job_id),
                    "policy_version": 1,
                    "species": species or _SPECIES,
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
            insert(candidate_enrichment_jobs).values(
                id=uuid4(),
                user_id=user_id,
                candidate_id=candidate_id,
                job_id=job_id,
                policy_version=1,
            )
        )
        await session.commit()
    return job_id, candidate_id


async def _seed_refresh(
    session_factory,
    *,
    species: dict,
    status: str = "pending",
    completed_at: datetime | None = None,
    result: dict | None = None,
    enrichment_job_ids: list[UUID] | None = None,
) -> UUID:
    """Seed a refresh job, optionally associated with causing enrichments.

    Without ``enrichment_job_ids`` the refresh has no causal association and
    must never appear in activity results.
    """
    job_id = uuid4()
    now = _now()
    if completed_at is not None:
        now = min(now, completed_at)
    async with session_factory() as session:
        await session.execute(
            insert(application_jobs).values(
                id=job_id,
                user_id=None,
                job_type="refresh_profile",
                payload_version=1,
                payload={
                    "policy_version": 1,
                    "species": species,
                    "fingerprint": "fp",
                    "run_id": str(job_id),
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
                insert(profile_refresh_enrichment_jobs).values(
                    refresh_job_id=job_id,
                    enrichment_job_id=enrichment_job_id,
                )
            )
        await session.commit()
    return job_id


async def _activity(session_factory, *, user_id: UUID, limit: int = 20):
    async with session_factory() as session:
        return await JobRepository(session).get_enrichment_activity(
            user_id=user_id,
            limit=limit,
            terminal_retention_window=RETENTION,
        )


async def test_active_enrichment_listed_with_context_without_payload_leak(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    job_id, candidate_id = await _seed_enrichment(
        session_factory, user_id=user_id, status="processing"
    )

    items, has_more = await _activity(session_factory, user_id=user_id)
    assert has_more is False
    assert len(items) == 1
    item = items[0]
    assert item.id == job_id
    assert item.job_type is JobType.enrich_confirmed_plant
    assert item.phase is EnrichmentActivityPhase.evidence
    assert item.status.value == "processing"
    assert item.candidate_id == candidate_id
    assert item.scientific_name == "Monstera deliciosa"
    assert item.species_key == "gbif:2878688|binomial:Monstera deliciosa"
    assert item.created_at is not None
    assert item.completed_at is None
    assert item.result is None


async def test_terminal_enrichment_within_retention_is_returned(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    job_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        completed_at=_now() - timedelta(hours=1),
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

    items, _ = await _activity(session_factory, user_id=user_id)
    assert [item.id for item in items] == [job_id]
    item = items[0]
    assert item.status.value == "complete"
    assert item.completed_at is not None
    assert item.result is not None
    assert item.result.outcome == "complete"
    assert item.result.covered_count == 1
    assert item.result.missing_count == 0
    assert item.result.limitations == []


async def test_terminal_enrichment_outside_retention_is_excluded(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        completed_at=_now() - RETENTION - timedelta(minutes=1),
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

    items, _ = await _activity(session_factory, user_id=user_id)
    assert items == []


async def test_failed_job_exposes_sanitized_error_only(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    job_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="failed",
        completed_at=_now() - timedelta(minutes=5),
        last_error={"category": "attempts_exhausted", "retryable": False},
    )

    items, _ = await _activity(session_factory, user_id=user_id)
    item = items[0]
    assert item.id == job_id
    assert item.result is None
    assert item.last_error is not None
    assert item.last_error.category is JobFailureCategory.attempts_exhausted
    assert item.last_error.retryable is False


async def test_foreign_owner_activity_is_isolated(session_factory):
    owner = uuid4()
    foreign = uuid4()
    await _seed_user(session_factory, user_id=owner, suffix="a.invalid")
    await _seed_user(session_factory, user_id=foreign, suffix="b.invalid")
    await _seed_enrichment(session_factory, user_id=owner, status="processing")

    foreign_items, _ = await _activity(session_factory, user_id=foreign)
    assert foreign_items == []
    owner_items, _ = await _activity(session_factory, user_id=owner)
    assert len(owner_items) == 1


async def test_shared_job_across_candidates_is_deduplicated(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    job_id, _ = await _seed_enrichment(
        session_factory, user_id=user_id, status="pending"
    )
    # A second candidate of the same species shares the same durable job.
    second_candidate_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(identification_candidates).values(
                id=second_candidate_id,
                user_id=user_id,
                suggested_scientific_name="Monstera deliciosa",
                accepted_scientific_name="Monstera deliciosa",
                binomial_name="Monstera deliciosa",
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Possible match.",
                taxonomic_status="ACCEPTED",
                synonyms=[],
                validation_status="validated",
            )
        )
        await session.execute(
            insert(candidate_enrichment_jobs).values(
                id=uuid4(),
                user_id=user_id,
                candidate_id=second_candidate_id,
                job_id=job_id,
                policy_version=1,
            )
        )
        await session.commit()

    items, _ = await _activity(session_factory, user_id=user_id)
    assert len(items) == 1
    assert items[0].id == job_id


async def test_refresh_profile_following_owner_enrichment_is_included(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    enrich_id, candidate_id = await _seed_enrichment(
        session_factory, user_id=user_id, status="complete",
        completed_at=_now() - timedelta(minutes=10),
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
        session_factory,
        species=_SPECIES,
        status="processing",
        result=None,
        enrichment_job_ids=[enrich_id],
    )

    items, _ = await _activity(session_factory, user_id=user_id)
    by_id = {item.id: item for item in items}
    assert set(by_id) == {enrich_id, refresh_id}
    refresh = by_id[refresh_id]
    assert refresh.phase is EnrichmentActivityPhase.profile_refresh
    assert refresh.job_type is JobType.refresh_profile
    # The refresh carries the authorized owner-candidate context.
    assert refresh.candidate_id == candidate_id
    assert refresh.scientific_name == "Monstera deliciosa"
    assert refresh.species_key == "gbif:2878688|binomial:Monstera deliciosa"


async def test_refresh_profile_for_unrelated_species_is_excluded(session_factory):
    user_id = uuid4()
    foreign_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    await _seed_user(session_factory, user_id=foreign_id, suffix="other.invalid")
    enrich_id, _ = await _seed_enrichment(
        session_factory, user_id=user_id, status="processing"
    )
    # A refresh causally tied only to a foreign enrichment run must never be
    # surfaced to this owner, even when the payload species matches.
    await _seed_refresh(
        session_factory,
        species=_OTHER_SPECIES,
        status="processing",
        enrichment_job_ids=[await _foreign_enrichment_id(
            session_factory, user_id=foreign_id
        )],
    )

    items, _ = await _activity(session_factory, user_id=user_id)
    assert [item.id for item in items] == [enrich_id]


async def _foreign_enrichment_id(session_factory, *, user_id: UUID) -> UUID:
    job_id, _ = await _seed_enrichment(
        session_factory, user_id=user_id, status="complete"
    )
    return job_id


async def test_bounded_cap_reports_has_more(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    now = _now()
    for index in range(5):
        job_id = uuid4()
        candidate_id = uuid4()
        async with session_factory() as session:
            await session.execute(
                insert(identification_images).values(
                    id=uuid4(),
                    user_id=user_id,
                    storage_path=f"p{index}.jpg",
                    mime_type="image/jpeg",
                    size_bytes=10,
                    metadata={},
                    status="needs_confirmation",
                )
            )
            await session.execute(
                insert(identification_candidates).values(
                    id=candidate_id,
                    user_id=user_id,
                    suggested_scientific_name=f"Species {index}",
                    accepted_scientific_name=f"Species {index}",
                    confidence_label="high",
                    visible_traits=[],
                    possible_match_copy="Possible match.",
                    taxonomic_status="ACCEPTED",
                    synonyms=[],
                    validation_status="validated",
                )
            )
            await session.execute(
                insert(application_jobs).values(
                    id=job_id,
                    user_id=user_id,
                    job_type="enrich_confirmed_plant",
                    payload_version=1,
                    payload={
                        "run_id": str(job_id),
                        "policy_version": 1,
                        "species": {
                            "accepted_gbif_key": None,
                            "normalized_binomial": f"Species {index}",
                        },
                    },
                    status="pending",
                    idempotency_key=f"enrich-cap-{uuid4()}",
                    attempt_count=1,
                    max_attempts=3,
                    created_at=now - timedelta(minutes=index),
                    updated_at=now - timedelta(minutes=index),
                )
            )
            await session.execute(
                insert(candidate_enrichment_jobs).values(
                    id=uuid4(),
                    user_id=user_id,
                    candidate_id=candidate_id,
                    job_id=job_id,
                    policy_version=1,
                )
            )
            await session.commit()

    items, has_more = await _activity(session_factory, user_id=user_id, limit=3)
    assert len(items) == 3
    assert has_more is True
    # Newest first.
    assert items[0].created_at.replace(tzinfo=None) == now.replace(tzinfo=None)


async def test_empty_activity_for_unknown_user(session_factory):
    user_id = uuid4()
    items, has_more = await _activity(session_factory, user_id=user_id)
    assert items == []
    assert has_more is False


async def test_refresh_profile_without_owner_enrichment_is_never_returned(session_factory):
    # A user who only ever produced a profile-refresh signal for a species has
    # no candidate enrichment in scope, so the refresh job must stay hidden.
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    await _seed_refresh(session_factory, species=_SPECIES, status="processing")

    items, _ = await _activity(session_factory, user_id=user_id)
    assert items == []

async def test_active_job_older_than_retention_remains_visible(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    old_stamp = _now() - RETENTION - timedelta(days=30)
    job_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="processing",
        updated_at=old_stamp,
    )

    items, _ = await _activity(session_factory, user_id=user_id)
    assert [item.id for item in items] == [job_id]


async def test_terminal_job_without_completed_at_stays_hidden(session_factory):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    stamp = _now() - timedelta(minutes=5)
    async with session_factory() as session:
        await session.execute(
            insert(application_jobs).values(
                id=(job_id := uuid4()),
                user_id=user_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={"run_id": str(job_id), "species": _SPECIES},
                # Terminal-looking status but no durable completion time:
                # this row must never surface as recent activity.
                status="complete",
                idempotency_key=f"null-complete-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=stamp,
                updated_at=stamp,
                completed_at=None,
            )
        )
        await session.commit()

    items, _ = await _activity(session_factory, user_id=user_id)
    assert items == []


async def test_retention_boundary_is_inclusive_at_exact_cutoff(
    session_factory, monkeypatch
):
    """A terminal job completed exactly at the cutoff stays within retention."""
    from datetime import datetime

    import app.jobs.repository as repo_module

    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")

    frozen_now = _now() - timedelta(minutes=1)
    completed_at = frozen_now - RETENTION

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return frozen_now if tz is None else frozen_now.astimezone(tz)

    monkeypatch.setattr(repo_module, "datetime", _FrozenDatetime)

    job_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        completed_at=completed_at,
        updated_at=completed_at,
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

    items, has_more = await _activity(session_factory, user_id=user_id)
    assert [item.id for item in items] == [job_id]
    assert has_more is False


async def test_result_policy_is_phase_and_status_consistent(session_factory):
    """Corrupt or contradictory result metadata degrades to ``None``."""
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="policy")

    cases: list[tuple[str, str, dict, bool, str | None]] = [
        # (status, outcome, extra counts, expect result, expected outcome)
        ("complete", "noop", {}, False, None),
        ("complete", "partial", {}, False, None),
        ("pending", "complete", {}, False, None),
        ("processing", "complete", {}, False, None),
        ("failed", "complete", {}, False, None),
        ("complete", "complete", {"covered_count": 2}, True, "complete"),
        ("partial", "partial", {"missing_count": 3}, True, "partial"),
    ]
    seeded_ids: list[UUID] = []
    for status, outcome, counts, _, _ in cases:
        terminal = status in {"complete", "partial", "failed"}
        job_id, _ = await _seed_enrichment(
            session_factory,
            user_id=user_id,
            status=status,
            completed_at=_now() if terminal else None,
            result={"outcome": outcome, **counts},
        )
        seeded_ids.append(job_id)

    refresh_complete = await _seed_refresh(
        session_factory,
        species=_SPECIES,
        status="complete",
        completed_at=_now(),
        result={"outcome": "partial"},
        enrichment_job_ids=[seeded_ids[0]],
    )
    refresh_ok = await _seed_refresh(
        session_factory,
        species=_SPECIES,
        status="complete",
        completed_at=_now(),
        result={"outcome": "noop", "regenerated_sections": ["watering"]},
        enrichment_job_ids=[seeded_ids[0]],
    )

    activity_items, _ = await _activity(session_factory, user_id=user_id)
    items = {item.id: item for item in activity_items}

    for (status, outcome, _, expect_result, expected_outcome), job_id in zip(
        cases, seeded_ids, strict=True
    ):
        item = items[job_id]
        if expect_result:
            assert item.result is not None, f"{status}/{outcome}"
            assert item.result.outcome == expected_outcome
        else:
            assert item.result is None, f"{status}/{outcome}"

    assert items[refresh_complete].result is None  # partial outcome on complete
    refreshed = items[refresh_ok]
    assert refreshed.result is not None
    assert refreshed.result.outcome == "noop"
    assert refreshed.result.regenerated_section_count == 1


async def test_evidence_results_never_surface_refresh_counts_and_vice_versa(
    session_factory,
):
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="phasesplit")

    evidence_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        completed_at=_now(),
        result={
            "outcome": "complete",
            "covered_count": 1,
            "regenerated_section_count": 9,
            "stale_section_count": 9,
        },
    )
    refresh_id = await _seed_refresh(
        session_factory,
        species=_SPECIES,
        status="complete",
        completed_at=_now(),
        result={
            "outcome": "complete",
            "covered_count": 7,
            "missing_count": 7,
            "regenerated_section_count": 2,
        },
        enrichment_job_ids=[evidence_id],
    )

    activity_items, _ = await _activity(session_factory, user_id=user_id)
    items = {item.id: item for item in activity_items}
    evidence = items[evidence_id].result
    assert evidence is not None
    assert evidence.covered_count == 1
    assert evidence.regenerated_section_count == 0
    assert evidence.stale_section_count == 0

    refresh = items[refresh_id].result
    assert refresh is not None
    assert refresh.regenerated_section_count == 2
    assert refresh.covered_count == 0
    assert refresh.missing_count == 0


def test_activity_schema_rejects_invalid_job_type_phase_combination():
    import pytest

    from app.jobs.schemas import EnrichmentActivityItem

    base = {
        "id": uuid4(),
        "status": "processing",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "scientific_name": "Monstera deliciosa",
        "candidate_id": uuid4(),
    }

    with pytest.raises(Exception, match="job type and phase"):
        EnrichmentActivityItem(
            **base,
            job_type=JobType.ingest_validated_claims,
            phase=EnrichmentActivityPhase.evidence,
        )
    with pytest.raises(Exception, match="job type and phase"):
        EnrichmentActivityItem(
            **base,
            job_type=JobType.enrich_confirmed_plant,
            phase=EnrichmentActivityPhase.profile_refresh,
        )


def test_retention_setting_rejects_out_of_range_values(monkeypatch):
    from app.core.settings import Settings

    def setting_for(value: str) -> int:
        monkeypatch.setenv("ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS", value)
        return Settings().enrichment_activity_terminal_retention_hours

    for accepted in ("1", "24", "720"):
        assert setting_for(accepted) == int(accepted)

    for rejected in ("0", "721", "1000000"):
        try:
            monkeypatch.setenv("ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS", rejected)
            Settings()
        except Exception:
            continue
        raise AssertionError(f"{rejected} should have been rejected")


async def test_contradictory_lifecycle_rows_are_excluded_not_fatal(session_factory):
    """Legacy rows violating timestamp invariants never break the page."""
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="lifecycle")
    now = _now()

    good_id, _ = await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        completed_at=now,
    )

    # A completion preceding creation: impossible lifecycle data.
    broken_job = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(application_jobs).values(
                id=broken_job,
                user_id=user_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={
                    "run_id": str(broken_job),
                    "policy_version": 1,
                    "species": _SPECIES,
                },
                status="complete",
                idempotency_key=f"enrich-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=now,
                updated_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=3),
            )
        )
        await session.execute(
            insert(identification_images).values(
                id=uuid4(),
                user_id=user_id,
                storage_path="broken.jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                metadata={},
                status="needs_confirmation",
            )
        )
        broken_candidate = uuid4()
        await session.execute(
            insert(identification_candidates).values(
                id=broken_candidate,
                identification_id=None,
                user_id=user_id,
                suggested_scientific_name="Broken chronology",
                accepted_scientific_name="Broken chronology",
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Possible match.",
                taxonomic_status="ACCEPTED",
                synonyms=[],
                validation_status="validated",
            )
        )
        await session.execute(
            insert(candidate_enrichment_jobs).values(
                id=uuid4(),
                user_id=user_id,
                candidate_id=broken_candidate,
                job_id=broken_job,
                policy_version=1,
            )
        )
        await session.commit()

    activity_items, _ = await _activity(session_factory, user_id=user_id)
    assert [item.id for item in activity_items] == [good_id]


async def test_completed_at_following_updated_at_is_excluded(session_factory):
    """A terminal row whose completion follows its last update is malformed and
    sanitized out, consistent with other broken lifecycle metadata."""
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    now = _now()
    await _seed_enrichment(
        session_factory,
        user_id=user_id,
        status="complete",
        updated_at=now - timedelta(hours=1),
        completed_at=now,  # completed_at > updated_at: malformed
        result={
            "outcome": "complete",
            "covered_count": 1,
            "missing_count": 0,
            "regenerated_section_count": 0,
            "stale_section_count": 0,
            "limitations": [],
        },
    )

    items, has_more = await _activity(session_factory, user_id=user_id)
    assert items == []
    assert has_more is False


async def test_malformed_run_keeps_deeper_valid_rows_reachable(session_factory):
    """A run of newer malformed lifecycle rows must not hide older valid rows
    or flip ``has_more`` false, so the batching re-advances the keyset cursor."""
    user_id = uuid4()
    await _seed_user(session_factory, user_id=user_id, suffix="test.invalid")
    now = _now()
    base = now - timedelta(hours=2)
    result = {
        "outcome": "complete",
        "covered_count": 1,
        "missing_count": 0,
        "regenerated_section_count": 0,
        "stale_section_count": 0,
        "limitations": [],
    }
    # limit + 5 = 6 malformed rows (limit = 1), newer than the valid rows below.
    for index in range(6):
        await _seed_enrichment(
            session_factory,
            user_id=user_id,
            status="complete",
            updated_at=base + timedelta(minutes=index),
            completed_at=base + timedelta(minutes=index + 10),
            result=result,
        )
    valid_ids = []
    for index in range(2):  # more than limit so has_more is genuinely true
        job_id, _ = await _seed_enrichment(
            session_factory,
            user_id=user_id,
            status="complete",
            updated_at=base - timedelta(minutes=index),
            completed_at=base - timedelta(minutes=index),
            result=result,
        )
        valid_ids.append(job_id)

    items, has_more = await _activity(session_factory, user_id=user_id, limit=1)
    assert has_more is True
    assert items, "deeper valid rows must stay reachable past malformed rows"
    assert items[0].id in valid_ids
    assert items[0].status == "complete"
