from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text, update

from app.auth.tables import application_jobs
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    IngestValidatedClaimsPayload,
    JobError,
    JobFailureCategory,
    JobStatus,
    JobType,
)


_VALID_JOB_TYPE = JobType.ingest_validated_claims.value


def _valid_payload_data() -> dict:
    return {
        "claims": [
            {
                "scientific_name": "Cotyledon tomentosa",
                "topic": "watering",
                "source_url": "https://example.org/watering",
                "source_domain": "example.org",
                "source_provenance": "trusted",
                "claim": "Water when the substrate dries.",
                "evidence_quote": "Allow the substrate to dry before watering.",
                "confidence": 0.9,
                "covered_aspects": ["watering_frequency_or_trigger"],
                "answerability_status": "full",
            }
        ],
        "conversation_id": str(uuid4()),
        "answerability_status": "full",
    }


def test_validated_claim_payload_rejects_empty_claims() -> None:
    data = _valid_payload_data()
    data["claims"] = []
    with pytest.raises(ValidationError):
        IngestValidatedClaimsPayload.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "scientific_name",
        "topic",
        "source_domain",
        "claim",
        "evidence_quote",
    ],
)
def test_validated_claim_payload_rejects_whitespace_required_fields(field: str) -> None:
    data = _valid_payload_data()
    data["claims"][0][field] = "   "
    with pytest.raises(ValidationError):
        IngestValidatedClaimsPayload.model_validate(data)


def test_validated_claim_payload_normalizes_text_and_aspects() -> None:
    data = _valid_payload_data()
    claim = data["claims"][0]
    for field in ("scientific_name", "topic", "source_domain", "claim", "evidence_quote"):
        claim[field] = f"  {claim[field]}  "
    claim["covered_aspects"] = ["  watering_frequency_or_trigger  "]
    claim["required_aspects"] = ["  watering_frequency_or_trigger  "]

    parsed = IngestValidatedClaimsPayload.model_validate(data)

    assert parsed.claims[0].scientific_name == "Cotyledon tomentosa"
    assert parsed.claims[0].topic == "watering"
    assert parsed.claims[0].source_domain == "example.org"
    assert parsed.claims[0].covered_aspects == ["watering_frequency_or_trigger"]
    assert parsed.claims[0].required_aspects == ["watering_frequency_or_trigger"]


@pytest.mark.parametrize("aspect_field", ["covered_aspects", "required_aspects", "missing_aspects"])
def test_validated_claim_payload_rejects_blank_aspects(aspect_field: str) -> None:
    data = _valid_payload_data()
    data["claims"][0][aspect_field] = ["   "]
    with pytest.raises(ValidationError):
        IngestValidatedClaimsPayload.model_validate(data)


def test_validated_claim_payload_forbids_additional_fields() -> None:
    data = _valid_payload_data()
    data["claims"][0]["raw_prompt"] = "must not persist"
    with pytest.raises(ValidationError):
        IngestValidatedClaimsPayload.model_validate(data)


async def test_enqueue_creates_pending_job(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE,
            payload_version=1,
            payload={"key": "value"},
            idempotency_key="test-key-1",
        )
        await session.commit()

        row = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.id == job_id)
            )
        ).first()
    assert row is not None
    assert row._mapping["job_type"] == _VALID_JOB_TYPE
    assert row._mapping["status"] == "pending"
    assert row._mapping["payload_version"] == 1
    assert row._mapping["payload"] == {"key": "value"}
    assert row._mapping["idempotency_key"] == "test-key-1"
    assert row._mapping["attempt_count"] == 0


async def test_enqueue_idempotency_reuses_existing_job(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id1 = await repo.enqueue(
            job_type=_VALID_JOB_TYPE,
            payload_version=1,
            payload={"a": 1},
            idempotency_key="dup-key",
        )
        job_id2 = await repo.enqueue(
            job_type=_VALID_JOB_TYPE,
            payload_version=1,
            payload={"a": 2},
            idempotency_key="dup-key",
        )
        await session.commit()
    assert job_id1 == job_id2


async def test_enqueue_with_user_ownership(session_factory) -> None:
    user_id = uuid4()
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE,
            payload_version=1,
            payload={},
            idempotency_key="user-key",
            user_id=user_id,
        )
        await session.commit()

        row = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.id == job_id)
            )
        ).first()
    assert row._mapping["user_id"] == user_id


async def _set_processing(session, job_id, owner="w1"):
    token = str(uuid4())
    await session.execute(
        update(application_jobs)
        .where(application_jobs.c.id == job_id)
        .values(
            status="processing",
            lease_owner=owner,
            lease_token=token,
            lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
        )
    )
    return token


async def _get_token(session, job_id) -> str:
    row = (
        await session.execute(
            select(application_jobs.c.lease_token).where(application_jobs.c.id == job_id)
        )
    ).first()
    return row._mapping["lease_token"]


async def test_complete_job_updates_status(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
            idempotency_key="complete-test",
        )
        await session.commit()

    async with session_factory() as session:
        await _set_processing(session, job_id)
        await session.commit()

    async with session_factory() as session:
        token = await _get_token(session, job_id)
        repo = JobRepository(session)
        success = await repo.complete_job(
            job_id=job_id, owner="w1", lease_token=token
        )
        await session.commit()

    assert success is True

    async with session_factory() as session:
        row = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.id == job_id)
            )
        ).first()
    assert row._mapping["status"] == "complete"
    assert row._mapping["completed_at"] is not None


async def test_stale_owner_cannot_finalize(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
            idempotency_key="stale-test",
        )
        await session.commit()

    async with session_factory() as session:
        await _set_processing(session, job_id, owner="w1")
        await session.commit()

    async with session_factory() as session:
        token = await _get_token(session, job_id)
        repo = JobRepository(session)
        success = await repo.complete_job(
            job_id=job_id, owner="w2", lease_token=token
        )
        await session.commit()
    assert success is False


async def test_stale_token_cannot_finalize(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
            idempotency_key="stale-token-test",
        )
        await session.commit()

    async with session_factory() as session:
        await _set_processing(session, job_id, owner="w1")
        await session.commit()

    async with session_factory() as session:
        repo = JobRepository(session)
        success = await repo.complete_job(
            job_id=job_id, owner="w1", lease_token=str(uuid4())
        )
        await session.commit()
    assert success is False


async def test_fail_job_updates_status(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
            idempotency_key="fail-test",
        )
        await session.commit()

    async with session_factory() as session:
        await _set_processing(session, job_id)
        await session.commit()

    async with session_factory() as session:
        token = await _get_token(session, job_id)
        repo = JobRepository(session)
        success = await repo.fail_job(
            job_id=job_id, owner="w1", lease_token=token,
            error=JobError(
                category=JobFailureCategory.unexpected_error,
                retryable=False,
            ),
        )
        await session.commit()

    assert success is True

    async with session_factory() as session:
        row = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.id == job_id)
            )
        ).first()
    assert row._mapping["status"] == "failed"
    assert row._mapping["last_error"]["category"] == "unexpected_error"


async def test_retry_job_reschedules(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
            idempotency_key="retry-test",
        )
        await session.commit()

    async with session_factory() as session:
        await _set_processing(session, job_id)
        await session.commit()

    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    async with session_factory() as session:
        token = await _get_token(session, job_id)
        repo = JobRepository(session)
        success = await repo.retry_job(
            job_id=job_id, owner="w1", lease_token=token,
            error=JobError(
                category=JobFailureCategory.provider_transient,
                retryable=True,
            ),
            available_at=future,
        )
        await session.commit()

    assert success is True

    async with session_factory() as session:
        row = (
            await session.execute(
                select(application_jobs).where(application_jobs.c.id == job_id)
            )
        ).first()
    assert row._mapping["status"] == "pending"


async def test_get_job_status_owner_only(session_factory) -> None:
    user_id = uuid4()
    other_user = uuid4()
    async with session_factory() as session:
        repo = JobRepository(session)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1, payload={"secret": "data"},
            idempotency_key="status-test", user_id=user_id,
        )
        await session.commit()

    async with session_factory() as session:
        repo = JobRepository(session)
        status = await repo.get_job_status(job_id=job_id, user_id=user_id)
        assert status is not None
        assert status.job_type == _VALID_JOB_TYPE
        assert status.status == JobStatus.pending
        assert status.attempt_count == 0
        assert status.result is None
        assert status.last_error is None

        not_found = await repo.get_job_status(job_id=job_id, user_id=other_user)
        assert not_found is None


async def test_backlog_counts(session_factory) -> None:
    async with session_factory() as session:
        repo = JobRepository(session)
        for i in range(3):
            await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1, payload={},
                idempotency_key=f"bl-{i}",
            )
        await session.commit()

    async with session_factory() as session:
        repo = JobRepository(session)
        counts = await repo.get_backlog_counts()
    assert counts.get((_VALID_JOB_TYPE, "pending"), 0) == 3
