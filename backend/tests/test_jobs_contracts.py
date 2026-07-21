from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.jobs.repository import JobRepository, canonical_idempotency_key
from app.jobs.schemas import (
    LEGACY_V1_INGESTION_POLICY_VERSION,
    MAX_CLAIMS_PER_PAYLOAD,
    MAX_LIMITATIONS_PER_RESULT,
    IngestValidatedClaimsPayload,
    JobStatus,
    ReadJobResult,
)
from app.observability.metrics import MetricsRegistry


def test_durable_job_controls_default_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("JOBS_PRODUCER_ENABLED", raising=False)
    monkeypatch.delenv("JOBS_WORKER_ENABLED", raising=False)

    settings = Settings()

    assert settings.jobs_producer_enabled is False
    assert settings.jobs_worker_enabled is False


def test_read_job_result_enforces_documented_bounds() -> None:
    assert ReadJobResult(succeeded=MAX_CLAIMS_PER_PAYLOAD).succeeded == (
        MAX_CLAIMS_PER_PAYLOAD
    )
    assert len(
        ReadJobResult(
            limitations=["some_claims_failed"] * MAX_LIMITATIONS_PER_RESULT
        ).limitations
    ) == MAX_LIMITATIONS_PER_RESULT

    for invalid_count in (-1, MAX_CLAIMS_PER_PAYLOAD + 1):
        with pytest.raises(ValidationError):
            ReadJobResult(succeeded=invalid_count)
    with pytest.raises(ValidationError):
        ReadJobResult(
            limitations=["some_claims_failed"] * (MAX_LIMITATIONS_PER_RESULT + 1)
        )
    with pytest.raises(ValidationError):
        ReadJobResult(limitations=["not-a-closed-limitation"])


def test_status_deserialization_rejects_corrupt_persisted_metadata() -> None:
    repository = JobRepository(AsyncMock())
    row = {
        "id": uuid4(),
        "job_type": "ingest_validated_claims",
        "status": JobStatus.failed.value,
        "attempt_count": 1,
        "max_attempts": 3,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "last_error": {"category": "malformed-category", "retryable": False},
        "result": None,
    }
    with pytest.raises(ValidationError):
        repository._row_to_status_response(row)

    row["last_error"] = None
    row["result"] = {"succeeded": MAX_CLAIMS_PER_PAYLOAD + 1}
    with pytest.raises(ValidationError):
        repository._row_to_status_response(row)


async def test_enqueue_rejects_nonpositive_attempt_limits_before_sql() -> None:
    session = AsyncMock()
    repository = JobRepository(session)
    for limit in (0, -1):
        with pytest.raises(ValueError, match="at least 1"):
            await repository.enqueue_result(
                job_type="ingest_validated_claims",
                payload_version=1,
                payload={},
                idempotency_key=f"invalid-attempt-limit-{limit}",
                max_attempts=limit,
            )
    session.execute.assert_not_awaited()


def test_schedule_and_status_metrics_are_closed_and_payload_safe() -> None:
    registry = MetricsRegistry()
    registry.record_job_schedule(
        job_type="ingest_validated_claims", outcome="created"
    )
    registry.record_job_schedule(
        job_type="ingest_validated_claims", outcome="reused"
    )
    registry.record_job_status_count(
        job_type="ingest_validated_claims", status="complete", count=4
    )
    rendered = registry.to_prometheus()

    assert 'fotosintesis_job_schedules_total{job_type="ingest_validated_claims",outcome="created"} 1' in rendered
    assert 'fotosintesis_job_schedules_total{job_type="ingest_validated_claims",outcome="reused"} 1' in rendered
    assert 'fotosintesis_job_status_count{job_type="ingest_validated_claims",status="complete"} 4' in rendered
    for forbidden in ("job_id", "user_id", "conversation_id", "https://", "payload"):
        assert forbidden not in rendered
    with pytest.raises(ValueError):
        registry.record_job_schedule(
            job_type="ingest_validated_claims", outcome="arbitrary"
        )
    with pytest.raises(ValueError):
        registry.record_job_status_count(
            job_type="ingest_validated_claims", status="arbitrary", count=1
        )


def _valid_payload_data() -> dict:
    return {
        "payload_version": 1,
        "claims": [
            {
                "scientific_name": "Rosmarinus officinalis",
                "topic": "care",
                "source_url": "https://example.org/water",
                "source_domain": "example.org",
                "source_provenance": "trusted",
                "claim": "Water weekly",
                "evidence_quote": "Water once per week",
                "confidence": 0.95,
                "covered_aspects": ["watering"],
                "answerability_status": "full",
            }
        ],
        "conversation_id": "11111111-1111-1111-1111-111111111111",
        "answerability_status": "full",
    }


def test_v1_payload_without_policy_defaults_to_legacy_policy() -> None:
    data = _valid_payload_data()
    data.pop("ingestion_policy_version", None)

    parsed = IngestValidatedClaimsPayload.model_validate(data)

    assert parsed.ingestion_policy_version == LEGACY_V1_INGESTION_POLICY_VERSION
    assert (
        parsed.model_dump(mode="json")["ingestion_policy_version"]
        == LEGACY_V1_INGESTION_POLICY_VERSION
    )


@pytest.mark.parametrize("value", [None, 0, -1, "1", 1.5])
def test_invalid_policy_values_rejected(value: object) -> None:
    data = _valid_payload_data()
    data["ingestion_policy_version"] = value

    with pytest.raises(ValidationError):
        IngestValidatedClaimsPayload.model_validate(data)


def test_job_identity_separates_by_policy_version() -> None:
    conversation_id = UUID("22222222-2222-2222-2222-222222222222")
    claims_hash = "abc123"

    policy_1_key = canonical_idempotency_key(
        job_type="ingest_validated_claims",
        conversation_id=conversation_id,
        claims_hash=claims_hash,
        payload_version=1,
        ingestion_policy_version=1,
    )
    policy_2_key = canonical_idempotency_key(
        job_type="ingest_validated_claims",
        conversation_id=conversation_id,
        claims_hash=claims_hash,
        payload_version=1,
        ingestion_policy_version=2,
    )

    assert policy_1_key != policy_2_key


def test_claim_identity_separates_by_policy_version() -> None:
    from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

    claim: dict = {
        "scientific_name": "Rosmarinus officinalis",
        "topic": "care",
        "source_url": "https://example.org/water",
        "source_domain": "example.org",
        "source_provenance": "trusted",
        "claim": "Water weekly",
        "evidence_quote": "Water once per week",
        "covered_aspects": ["watering"],
    }

    policy_1_key = compute_claim_ingestion_key(
        claim, ingestion_policy_version=1
    )
    policy_2_key = compute_claim_ingestion_key(
        claim, ingestion_policy_version=2
    )

    assert policy_1_key.startswith("v1:")
    assert policy_2_key.startswith("v2:")
    assert policy_1_key != policy_2_key


def test_policy_1_identity_remains_stable() -> None:
    from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

    claim: dict = {
        "scientific_name": "Rosmarinus officinalis",
        "topic": "care",
        "source_url": "https://example.org/water",
        "source_domain": "example.org",
        "source_provenance": "trusted",
        "claim": "Water weekly",
        "evidence_quote": "Water once per week",
        "covered_aspects": ["watering"],
    }

    key = compute_claim_ingestion_key(claim, ingestion_policy_version=1)
    assert key.startswith("v1:")
    assert len(key) > 2
