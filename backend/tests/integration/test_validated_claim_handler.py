from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.auth.tables import (
    knowledge_chunks,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.assistant.tools.types import EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE
from app.core.settings import get_settings
from app.jobs.handler import RetryableJobError
from app.jobs.handlers import ingest_validated_claims as handler_module
from app.jobs.handlers.ingest_validated_claims import IngestValidatedClaimsHandler
from app.jobs.schemas import (
    IngestValidatedClaimsPayload,
    JobFailureCategory,
    JobLimitation,
    JobStatus,
)
from app.knowledge.rag import KnowledgeVectorIndex, LlamaIndexRuntime, VectorIndexError
from app.providers.errors import ProviderError
from app.providers.types import EmbeddingResult

from .conftest import BASE_DATABASE_URL


class _EmbeddingProvider:
    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        return EmbeddingResult(
            provider="integration",
            model="integration-8d",
            embeddings=[[0.1] * 8 for _ in texts],
        )


class _FailingEmbeddingProvider:
    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        raise ProviderError("provider unavailable")


def _payload(*, provenance: str = "trusted") -> IngestValidatedClaimsPayload:
    return IngestValidatedClaimsPayload.model_validate(
        {
            "payload_version": 1,
            "conversation_id": str(uuid4()),
            "answerability_status": "full",
            "claims": [
                {
                    "scientific_name": "Cotyledon tomentosa",
                    "topic": "watering",
                    "source_url": "https://example.org/watering",
                    "source_domain": "example.org",
                    "source_title": "Watering guide",
                    "source_provenance": provenance,
                    "claim": "Water when the substrate dries.",
                    "evidence_quote": "Allow the substrate to dry before watering.",
                    "confidence": 0.9,
                    "covered_aspects": ["watering_frequency_or_trigger"],
                    "required_aspects": ["watering_frequency_or_trigger"],
                    "missing_aspects": [],
                    "answerability_status": "full",
                    "language": "en",
                }
            ],
        }
    )


@pytest.fixture
async def vector_store(pg_schema):
    from llama_index.vector_stores.postgres import PGVectorStore

    url = make_url(BASE_DATABASE_URL)
    store = PGVectorStore.from_params(
        database=url.database,
        host=url.host,
        password=url.password,
        port=url.port,
        user=url.username,
        table_name="validated_claim_handler",
        schema_name=pg_schema,
        embed_dim=8,
        use_jsonb=True,
    )
    try:
        yield store
    finally:
        await store.close()


@pytest.fixture
def vector_index_factory(vector_store):
    runtime = LlamaIndexRuntime(
        get_settings(), vector_store_factory=lambda: vector_store
    )
    return lambda repository: KnowledgeVectorIndex(repository, runtime=runtime)


async def _counts(session_factory) -> tuple[int, int, int, int]:
    async with session_factory() as session:
        counts = []
        for table in (
            knowledge_documents,
            knowledge_sources,
            knowledge_chunks,
            knowledge_embeddings,
        ):
            counts.append(
                int(
                    await session.scalar(
                        select(func.count()).select_from(table)
                    )
                    or 0
                )
            )
        return tuple(counts)


def _handler(session_factory, vector_index_factory, provider=None):
    return IngestValidatedClaimsHandler(
        session_factory=session_factory,
        provider_registry_factory=lambda: SimpleNamespace(
            embeddings=provider or _EmbeddingProvider()
        ),
        vector_index_factory=vector_index_factory,
    )


@pytest.mark.parametrize(
    ("provenance", "expected_confidence"),
    [
        ("trusted", 0.9),
        ("external_fallback", EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE),
    ],
)
async def test_production_handler_persists_and_reuses_one_relational_and_vector_result(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provenance,
    expected_confidence,
) -> None:
    handler = _handler(pg_session_factory, vector_index_factory)

    first = await handler.handle(
        payload=_payload(provenance=provenance), attempt_count=1, max_attempts=3
    )
    second = await handler.handle(
        payload=_payload(provenance=provenance), attempt_count=2, max_attempts=3
    )

    assert first.status is JobStatus.complete
    assert first.result and first.result.succeeded == 1
    assert second.status is JobStatus.complete
    assert second.result and second.result.skipped == 1
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)

    async with pg_session_factory() as session:
        row = (
            await session.execute(
                select(
                    knowledge_documents.c.validated_claim_index_status,
                    knowledge_sources.c.validation_status,
                    knowledge_chunks.c.metadata,
                    knowledge_chunks.c.confidence,
                )
                .join(
                    knowledge_sources,
                    knowledge_sources.c.document_id == knowledge_documents.c.id,
                )
                .join(
                    knowledge_chunks,
                    knowledge_chunks.c.document_id == knowledge_documents.c.id,
                )
            )
        ).mappings().one()
    assert row["validated_claim_index_status"] == "complete"
    assert row["validation_status"] == provenance
    assert row["metadata"]["source_provenance"] == provenance
    assert row["confidence"] == expected_confidence

    chunk_ids = await _chunk_ids(pg_session_factory)
    nodes = await vector_store.aget_nodes(node_ids=[str(chunk_ids[0])])
    assert len(nodes) == 1
    metadata = nodes[0].metadata
    assert metadata["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert metadata["required_aspects"] == ["watering_frequency_or_trigger"]
    assert metadata["evidence_type"] == "validated_web_claim"
    assert metadata["answerability_status"] == "full"
    assert metadata["source_domain"] == "example.org"
    assert metadata["source_provenance"] == provenance
    assert metadata["confidence"] == expected_confidence


async def test_normalized_payload_values_are_stored_without_surrounding_whitespace(
    pg_session_factory,
    vector_index_factory,
) -> None:
    data = _payload().model_dump(mode="json")
    claim = data["claims"][0]
    for field in ("scientific_name", "topic", "source_domain", "claim", "evidence_quote"):
        claim[field] = f"  {claim[field]}  "
    claim["covered_aspects"] = ["  watering_frequency_or_trigger  "]
    payload = IngestValidatedClaimsPayload.model_validate(data)

    result = await _handler(pg_session_factory, vector_index_factory).handle(
        payload=payload,
        attempt_count=1,
        max_attempts=3,
    )

    assert result.status is JobStatus.complete
    async with pg_session_factory() as session:
        row = (
            await session.execute(
                select(
                    knowledge_documents.c.scientific_name,
                    knowledge_documents.c.topic,
                    knowledge_sources.c.source_domain,
                    knowledge_chunks.c.metadata,
                )
                .join(
                    knowledge_sources,
                    knowledge_sources.c.document_id == knowledge_documents.c.id,
                )
                .join(
                    knowledge_chunks,
                    knowledge_chunks.c.document_id == knowledge_documents.c.id,
                )
            )
        ).mappings().one()
    assert row["scientific_name"] == "Cotyledon tomentosa"
    assert row["topic"] == "watering"
    assert row["source_domain"] == "example.org"
    assert row["metadata"]["covered_aspects"] == ["watering_frequency_or_trigger"]


async def _chunk_ids(session_factory) -> list:
    async with session_factory() as session:
        return list((await session.scalars(select(knowledge_chunks.c.id))).all())


async def test_failure_before_relational_commit_leaves_both_stores_empty(
    pg_session_factory,
    vector_store,
    vector_index_factory,
) -> None:
    handler = _handler(
        pg_session_factory,
        vector_index_factory,
        provider=_FailingEmbeddingProvider(),
    )

    with pytest.raises(RetryableJobError) as raised:
        await handler.handle(payload=_payload(), attempt_count=1, max_attempts=3)

    assert raised.value.category is JobFailureCategory.provider_transient
    assert await _counts(pg_session_factory) == (0, 0, 0, 0)
    assert not await vector_store.aget_nodes(node_ids=[str(uuid4())])

    result = await _handler(pg_session_factory, vector_index_factory).handle(
        payload=_payload(), attempt_count=2, max_attempts=3
    )
    assert result.status is JobStatus.complete
    assert result.result and result.result.succeeded == 1
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)


async def test_permanent_claim_failure_returns_bounded_partial_result(
    pg_session_factory,
    vector_index_factory,
    monkeypatch,
) -> None:
    payload = _payload()
    invalid_claim = payload.claims[0].model_copy(
        update={
            "topic": "invalid",
            "claim": "A second claim that cannot be normalized.",
            "evidence_quote": "A distinct second quote.",
        }
    )
    payload = payload.model_copy(update={"claims": [payload.claims[0], invalid_claim]})
    build_document = handler_module.build_validated_claim_document

    def selectively_build(*, claim):
        if claim["topic"] == "invalid":
            return None
        return build_document(claim=claim)

    monkeypatch.setattr(
        handler_module,
        "build_validated_claim_document",
        selectively_build,
    )

    result = await _handler(pg_session_factory, vector_index_factory).handle(
        payload=payload, attempt_count=1, max_attempts=3
    )

    assert result.status is JobStatus.partial
    assert result.result is not None
    assert result.result.succeeded == 1
    assert result.result.failed == 1
    assert result.result.limitations == [JobLimitation.some_claims_failed]
    serialized_result = result.result.model_dump_json()
    for sensitive_value in (
        payload.claims[0].claim,
        payload.claims[0].evidence_quote,
        invalid_claim.claim,
        invalid_claim.evidence_quote,
    ):
        assert sensitive_value not in serialized_result
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)


async def test_retry_after_relational_commit_inserts_missing_vector_without_duplicates(
    pg_session_factory,
    vector_store,
    vector_index_factory,
) -> None:
    class _FailBeforeVector(KnowledgeVectorIndex):
        async def ensure_vector_nodes(self, **kwargs) -> None:
            raise VectorIndexError("injected before vector insert")

    def failing_factory(repository):
        return _FailBeforeVector(
            repository,
            runtime=vector_index_factory(repository).runtime,
        )

    with pytest.raises(RetryableJobError) as raised:
        await _handler(pg_session_factory, failing_factory).handle(
            payload=_payload(), attempt_count=1, max_attempts=3
        )
    assert raised.value.category is JobFailureCategory.indexing_transient
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)
    async with pg_session_factory() as session:
        status = await session.scalar(
            select(knowledge_documents.c.validated_claim_index_status)
        )
    assert status == "pending"

    result = await _handler(pg_session_factory, vector_index_factory).handle(
        payload=_payload(), attempt_count=2, max_attempts=3
    )
    assert result.status is JobStatus.complete
    assert result.result and result.result.succeeded == 1
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)
    nodes = await vector_store.aget_nodes(
        node_ids=[str(value) for value in await _chunk_ids(pg_session_factory)]
    )
    assert len(nodes) == 1


async def test_retry_after_vector_insert_reuses_node_id_and_marks_complete(
    pg_session_factory,
    vector_store,
    vector_index_factory,
) -> None:
    class _FailAfterVector(KnowledgeVectorIndex):
        async def mark_index_complete(self, document_id) -> None:
            raise VectorIndexError("injected after vector insert")

    def failing_factory(repository):
        return _FailAfterVector(
            repository,
            runtime=vector_index_factory(repository).runtime,
        )

    with pytest.raises(RetryableJobError):
        await _handler(pg_session_factory, failing_factory).handle(
            payload=_payload(), attempt_count=1, max_attempts=3
        )
    chunk_ids = await _chunk_ids(pg_session_factory)
    assert len(await vector_store.aget_nodes(node_ids=[str(value) for value in chunk_ids])) == 1

    result = await _handler(pg_session_factory, vector_index_factory).handle(
        payload=_payload(), attempt_count=2, max_attempts=3
    )
    assert result.status is JobStatus.complete
    assert await _counts(pg_session_factory) == (1, 1, 1, 1)
    assert len(await vector_store.aget_nodes(node_ids=[str(value) for value in chunk_ids])) == 1
    async with pg_session_factory() as session:
        assert (
            await session.scalar(
                select(knowledge_documents.c.validated_claim_index_status)
            )
        ) == "complete"
