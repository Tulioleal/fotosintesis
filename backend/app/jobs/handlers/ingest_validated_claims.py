from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.assistant.tools.ingestion import build_validated_claim_document
from app.core.settings import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.jobs.handler import (
    JobHandler,
    JobHandlerResult,
    PermanentJobError,
    RetryableJobError,
)
from app.jobs.schemas import (
    IngestValidatedClaimsPayload,
    JobFailureCategory,
    JobError,
    JobLimitation,
    JobStatus,
    ReadJobResult,
    SourceProvenance,
    LEGACY_V1_INGESTION_POLICY_VERSION,
)
from app.knowledge.rag import (
    KnowledgeVectorIndex,
    OrchestratedKnowledgeIngestion,
    VectorIndexError,
    build_pgvector_config,
)
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import ValidatedClaimIndexStatus
from app.providers.errors import ProviderError
from app.providers.factory import get_provider_registry
from app.providers.wrappers import AllProvidersFailedError

logger = logging.getLogger(__name__)


def validate_pgvector_runtime(config: object) -> None:
    if not config.database:
        raise ValueError("PGVector database is not configured")
    if not getattr(config, "embed_dim", 0) > 0:
        raise ValueError("PGVector embedding dimension must be positive")
    try:
        from llama_index.vector_stores.postgres import PGVectorStore  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("llama-index-vector-stores-postgres is not installed") from exc


def stable_document_id(ingestion_key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"validated-claim:{ingestion_key}")


def stable_chunk_id(ingestion_key: str, chunk_index: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"validated-claim:{ingestion_key}:chunk:{chunk_index}")


def _normalize_scientific_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_url(value: str) -> str:
    return value.strip().rstrip("/")


def compute_claim_ingestion_key(
    claim: dict[str, Any],
    *,
    ingestion_policy_version: int,
) -> str:
    source_provenance = SourceProvenance(str(claim["source_provenance"])).value
    normalized = {
        "scientific_name": _normalize_scientific_name(str(claim.get("scientific_name") or "")),
        "source_url": _normalize_url(str(claim.get("source_url") or "")),
        "source_domain": (str(claim.get("source_domain") or "")).strip().lower(),
        "source_provenance": source_provenance,
        "covered_aspects": sorted(
            {str(a).strip().lower() for a in (claim.get("covered_aspects") or [])}
        ),
        "claim": (str(claim.get("claim") or "")).strip(),
        "evidence_quote": (str(claim.get("evidence_quote") or "")).strip(),
        "ingestion_policy_version": ingestion_policy_version,
    }
    if ingestion_policy_version == LEGACY_V1_INGESTION_POLICY_VERSION:
        normalized["topic"] = (str(claim.get("topic") or "")).strip().lower()
    raw = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return f"v{ingestion_policy_version}:" + hashlib.sha256(raw.encode()).hexdigest()


class IngestValidatedClaimsHandler(JobHandler):
    def __init__(
        self,
        *,
        session_factory=AsyncSessionLocal,
        provider_registry_factory=get_provider_registry,
        vector_index_factory=KnowledgeVectorIndex,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider_registry_factory = provider_registry_factory
        self._providers = None
        self._vector_index_factory = vector_index_factory
        self._settings = settings or get_settings()

    def validate_dependencies(self) -> None:
        providers = self._provider_registry_factory()
        if providers.embeddings is None:
            raise ValueError("embedding provider was not configured")
        config = build_pgvector_config(self._settings)
        if not config.database or config.embed_dim <= 0:
            raise ValueError("PGVector configuration is incomplete")
        validate_pgvector_runtime(config)
        self._providers = providers

    async def handle(
        self, *, payload: BaseModel, attempt_count: int, max_attempts: int
    ) -> JobHandlerResult:
        parsed = payload
        assert isinstance(parsed, IngestValidatedClaimsPayload)

        policy_version = parsed.ingestion_policy_version

        claims = [c.model_dump(mode="json") for c in parsed.claims]
        providers = self._providers
        if providers is None:
            providers = self._provider_registry_factory()
            self._providers = providers
        succeeded = 0
        skipped = 0
        failed = 0
        last_failure_category = JobFailureCategory.invariant_violation
        for claim in claims:
            ingestion_key = compute_claim_ingestion_key(
                    claim,
                    ingestion_policy_version=policy_version,
                )
            async with self._session_factory() as session:
                try:
                    repo = KnowledgeRepository(session)
                    index = self._vector_index_factory(repo)
                    existing = await repo.get_validated_claim_state(ingestion_key)
                    if existing is not None:
                        chunk_ids = [chunk.id for chunk in existing.chunks if chunk.id]
                        if (
                            existing.index_status is ValidatedClaimIndexStatus.complete
                            and await index.has_all_nodes(chunk_ids)
                        ):
                            skipped += 1
                            continue
                        await index.ensure_vector_nodes(
                            chunks=existing.chunks,
                            embeddings=existing.embeddings,
                            provider=existing.embedding_provider,
                            model=existing.embedding_model,
                        )
                        await index.mark_index_complete(existing.document_id)
                        succeeded += 1
                        continue

                    document = build_validated_claim_document(claim=claim)
                    if document is None:
                        raise PermanentJobError(JobFailureCategory.invariant_violation)

                    document.metadata["claim_ingestion_key"] = ingestion_key
                    document.metadata["ingestion_policy_version"] = policy_version
                    document.metadata["source_provenance"] = claim.get(
                        "source_provenance"
                    )

                    document_id = stable_document_id(ingestion_key)
                    prepared = await index.prepare_document(
                        document, embedding_provider=providers.embeddings
                    )
                    ingestion = OrchestratedKnowledgeIngestion(
                        chunks=[
                            chunk.model_copy(
                                update={"id": stable_chunk_id(ingestion_key, i)}
                            )
                            for i, chunk in enumerate(prepared.chunks)
                        ],
                        embeddings=prepared.embeddings,
                        provider=prepared.provider,
                        model=prepared.model,
                    )
                    try:
                        persisted = await index.persist_relational(
                            document,
                            ingestion=ingestion,
                            ingestion_key=ingestion_key,
                            document_id=document_id,
                        )
                        chunks = persisted.chunks
                        embeddings = ingestion.embeddings
                        provider = ingestion.provider
                        model = ingestion.model
                    except IntegrityError as exc:
                        await session.rollback()
                        if not _is_expected_ingestion_key_conflict(exc):
                            raise RetryableJobError(
                                JobFailureCategory.database_transient
                            ) from exc
                        winner = await repo.get_validated_claim_state(ingestion_key)
                        if winner is None:
                            raise RetryableJobError(
                                JobFailureCategory.database_transient
                            ) from exc
                        document_id = winner.document_id
                        chunks = winner.chunks
                        embeddings = winner.embeddings
                        provider = winner.embedding_provider
                        model = winner.embedding_model

                    await index.ensure_vector_nodes(
                        chunks=chunks,
                        embeddings=embeddings,
                        provider=provider,
                        model=model,
                    )
                    await index.mark_index_complete(document_id)
                    succeeded += 1
                except PermanentJobError as exc:
                    await session.rollback()
                    failed += 1
                    last_failure_category = exc.category
                    continue
                except RetryableJobError as exc:
                    await session.rollback()
                    if attempt_count < max_attempts:
                        raise
                    failed += 1
                    last_failure_category = exc.category
                    continue
                except DBAPIError as exc:
                    await session.rollback()
                    if attempt_count < max_attempts:
                        raise RetryableJobError(
                            JobFailureCategory.database_transient
                        ) from exc
                    failed += 1
                    last_failure_category = JobFailureCategory.database_transient
                    continue
                except (ProviderError, AllProvidersFailedError) as exc:
                    await session.rollback()
                    if attempt_count < max_attempts:
                        raise RetryableJobError(
                            JobFailureCategory.provider_transient
                        ) from exc
                    failed += 1
                    last_failure_category = JobFailureCategory.provider_transient
                    continue
                except VectorIndexError as exc:
                    await session.rollback()
                    if attempt_count < max_attempts:
                        raise RetryableJobError(
                            JobFailureCategory.indexing_transient
                        ) from exc
                    failed += 1
                    last_failure_category = JobFailureCategory.indexing_transient
                    continue
                except ValueError:
                    await session.rollback()
                    failed += 1
                    last_failure_category = JobFailureCategory.invariant_violation
                    continue

        result = ReadJobResult(
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
            partial=failed > 0 and succeeded + skipped > 0,
            limitations=(
                [JobLimitation.some_claims_failed] if failed > 0 else []
            ),
        )
        if failed == 0:
            return JobHandlerResult(status=JobStatus.complete, result=result)
        if succeeded + skipped > 0:
            return JobHandlerResult(status=JobStatus.partial, result=result)
        return JobHandlerResult(
            status=JobStatus.failed,
            result=result,
            error=JobError(category=last_failure_category, retryable=False),
        )


def _is_expected_ingestion_key_conflict(exc: IntegrityError) -> bool:
    original = exc.orig
    constraint_name = getattr(original, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name in {
        "knowledge_documents_pkey",
        "uq_knowledge_documents_validated_claim_ingestion_key",
    }:
        return True
    # asyncpg's SQLAlchemy adapter does not always retain the constraint name,
    # but PostgreSQL's 23505 SQLSTATE is the typed unique-violation signal.
    return getattr(original, "sqlstate", None) == "23505"
