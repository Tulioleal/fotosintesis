from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from pydantic import BaseModel, ConfigDict
from typing import Literal

from app.core.settings import Settings
from app.jobs.repository import JobRepository, canonical_idempotency_key
from app.jobs.schemas import (
    LEGACY_V1_INGESTION_POLICY_VERSION,
    MAX_CLAIMS_PER_PAYLOAD,
    MAX_LIMITATIONS_PER_RESULT,
    IngestValidatedClaimsPayload,
    JobStatus,
    ReadJobResult,
    JobType,
)
from app.observability.metrics import MetricsRegistry
from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult


class _PayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload_version: Literal[1]
    value_v1: str


class _PayloadV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload_version: Literal[2]
    value_v2: int


class _NoopHandler(JobHandler):
    async def handle(self, *, payload, attempt_count, max_attempts) -> JobHandlerResult:
        raise AssertionError("not used")


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

    assert compute_claim_ingestion_key(claim, ingestion_policy_version=1) == (
        "v1:77f7f3d9fe2346568ea7252fd1c878af3336d568d7dbe83e8c296a6705c82163"
    )


def test_policy_2_identity_ignores_topic_drift() -> None:
    from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

    claim = _valid_payload_data()["claims"][0]
    changed_topic = {**claim, "topic": "irrigation"}

    assert compute_claim_ingestion_key(
        claim, ingestion_policy_version=2
    ) == compute_claim_ingestion_key(changed_topic, ingestion_policy_version=2)
    assert compute_claim_ingestion_key(
        claim, ingestion_policy_version=1
    ) != compute_claim_ingestion_key(changed_topic, ingestion_policy_version=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scientific_name", "Rosmarinus tomentosus"),
        ("source_url", "https://example.org/other"),
        ("source_domain", "other.example.org"),
        ("source_provenance", "external_fallback"),
        ("covered_aspects", ["light"]),
        ("claim", "Water only after the soil dries."),
        ("evidence_quote", "Wait for dry soil before watering."),
    ],
)
def test_policy_2_identity_keeps_documented_components(field: str, value: object) -> None:
    from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

    claim = _valid_payload_data()["claims"][0]
    original = compute_claim_ingestion_key(claim, ingestion_policy_version=2)

    assert compute_claim_ingestion_key(
        {**claim, field: value}, ingestion_policy_version=2
    ) != original


def test_handler_registry_validates_version_mapping() -> None:
    registry = HandlerRegistry()
    handler = _NoopHandler()
    with pytest.raises(ValueError, match="at least one payload version"):
        registry.register(JobType.ingest_validated_claims.value, handler, payload_models={})
    for version in (0, -1, True, False, "1", 1.5):
        with pytest.raises(ValueError):
            registry.register(
                JobType.ingest_validated_claims.value,
                handler,
                payload_models={version: _PayloadV1},
            )
    with pytest.raises(TypeError):
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: object},
        )


def test_handler_registry_resolves_multiple_payload_versions() -> None:
    registry = HandlerRegistry()
    handler = _NoopHandler()
    job_type = JobType.ingest_validated_claims.value
    registry.register(job_type, handler, payload_models={1: _PayloadV1, 2: _PayloadV2})
    assert registry.get_payload_model(job_type, 1) is _PayloadV1
    assert registry.get_payload_model(job_type, 2) is _PayloadV2


def test_handler_registry_rejects_unknown_job_type() -> None:
    with pytest.raises(ValueError):
        HandlerRegistry().register("unknown", _NoopHandler(), payload_models={1: _PayloadV1})


def test_handler_registry_duplicate_rules_preserve_compatibility() -> None:
    class _OtherHandler(_NoopHandler):
        pass

    registry = HandlerRegistry()
    job_type = JobType.ingest_validated_claims.value
    original = _NoopHandler()
    registry.register(job_type, original, payload_models={1: _PayloadV1, 2: _PayloadV2})
    registry.register(job_type, _NoopHandler(), payload_models={1: _PayloadV1, 2: _PayloadV2})
    assert registry.get_handler(job_type) is original
    for handler, models in (
        (_OtherHandler(), {1: _PayloadV1, 2: _PayloadV2}),
        (_NoopHandler(), {1: _PayloadV1}),
        (_NoopHandler(), {1: _PayloadV1, 2: _PayloadV2, 3: _PayloadV1}),
        (_NoopHandler(), {1: _PayloadV2, 2: _PayloadV2}),
    ):
        with pytest.raises(ValueError, match="already registered"):
            registry.register(job_type, handler, payload_models=models)
