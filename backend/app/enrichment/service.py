from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

from app.assistant.care_contracts import RequiredAspect
from app.assistant.semantic_coverage import (
    CoverageThresholds,
    SemanticCoverageService,
    SemanticEvidence,
    SemanticJudgeRequest,
    SemanticSourceEvidence,
)
from app.core.settings import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.enrichment.acquisition import OfflineEnrichmentAcquisitionService
from app.enrichment.evidence import (
    AcceptedEnrichmentClaim,
    EnrichmentEvidencePersistenceService,
)
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import get_enrichment_policy
from app.jobs.schemas import EnrichConfirmedPlantPayload
from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.rag import KnowledgeVectorIndex
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import KnowledgeRetrievalFilters
from app.providers.factory import ProviderRegistry, get_provider_registry

MAX_JUDGE_EVIDENCE_CHARS = 12_000
MAX_JUDGE_SOURCES = 20


def _bounded_evidence_sources(
    local: SemanticEvidence,
    acquired: SemanticEvidence | None,
) -> list[dict[str, object]]:
    """Build judge input as source-separated packages.

    Each entry keeps its canonical URL attached to its own truncated text so
    a support item can never bind to text detached from its source. The total
    character budget stays bounded by ``MAX_JUDGE_EVIDENCE_CHARS`` and the
    number of entries by ``MAX_JUDGE_SOURCES``.
    """
    ordered = [
        *(acquired.sources if acquired else ()),
        *local.sources,
    ]
    if not ordered:
        return []
    visible_count = min(len(ordered), MAX_JUDGE_SOURCES)
    budget_per_source = max(MAX_JUDGE_EVIDENCE_CHARS // visible_count, 1)

    bounded: list[dict[str, object]] = []
    for index, package in enumerate(ordered[:MAX_JUDGE_SOURCES]):
        url = str(package.metadata.get("url") or "").strip()
        entry = dict(package.metadata)
        entry["url"] = url
        entry["validation_status"] = package.metadata.get("validation_status")
        entry["text"] = package.text[:budget_per_source]
        entry["source_package_id"] = f"source-{index}"
        bounded.append(entry)
    return bounded


@dataclass(frozen=True)
class EnrichmentExecution:
    covered_aspects: tuple[RequiredAspect, ...]
    missing_aspects: tuple[RequiredAspect, ...]
    acquisition_avoided: bool
    safety_evidence_rejected: bool = False
    local_covered_count: int = 0
    search_count: int = 0
    accepted_aspect_count: int = 0


class EnrichmentExecutionService(Protocol):
    async def execute(self, payload: EnrichConfirmedPlantPayload) -> EnrichmentExecution: ...


class ProductionEnrichmentService:
    def __init__(
        self,
        *,
        session_factory=AsyncSessionLocal,
        providers: ProviderRegistry | None = None,
        settings: Settings | None = None,
        coverage: SemanticCoverageService | None = None,
        policy_resolver=get_enrichment_policy,
        vector_index_factory=KnowledgeVectorIndex,
    ) -> None:
        self._session_factory = session_factory
        self._providers = providers or get_provider_registry()
        self._settings = settings or get_settings()
        self._coverage = coverage or SemanticCoverageService()
        self._policy_resolver = policy_resolver
        self._vector_index_factory = vector_index_factory

    async def execute(self, payload: EnrichConfirmedPlantPayload) -> EnrichmentExecution:
        policy = self._policy_resolver(payload.policy_version)
        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=payload.species.accepted_gbif_key,
            normalized_binomial=payload.species.normalized_binomial,
            taxonomy_validated=True,
        )
        required = tuple(
            aspect for aspect in RequiredAspect if aspect in policy.required_aspects
        )
        thresholds = CoverageThresholds(
            default=self._settings.assistant_evidence_validation_threshold,
            safety=self._settings.assistant_safety_validation_threshold,
            strong_full=self._settings.assistant_strong_answer_validation_threshold,
        )

        async with self._session_factory() as session:
            repository = KnowledgeRepository(session, self._settings)
            vector_index = self._vector_index_factory(repository)

            async def retrieve(aspects: tuple[RequiredAspect, ...]) -> SemanticEvidence:
                query = " ".join(
                    [identity.normalized_binomial or "", *(item.value for item in aspects)]
                )
                embedding = await self._providers.embeddings.create_embeddings([query])
                query_embedding = embedding.embeddings[0] if embedding.embeddings else []
                chunks = await vector_index.retrieve_chunks(
                    KnowledgeRetrievalFilters(
                        scientific_name=identity.normalized_binomial,
                    ),
                    query_text=query,
                    query_embedding=query_embedding,
                    limit=24,
                )
                return SemanticEvidence(
                    sources=tuple(
                        SemanticSourceEvidence(
                            text=chunk.content,
                            metadata={
                                "url": chunk.source_url,
                                "domain": chunk.source_domain,
                                "confidence": chunk.confidence,
                                "validation_status": chunk.metadata.get(
                                    "validation_status"
                                ),
                            },
                        )
                        for chunk in chunks
                    ),
                    eligible_validation_statuses=frozenset({"trusted"}),
                )

            async def judge(request: SemanticJudgeRequest):
                evidence_sources = _bounded_evidence_sources(
                    request.local_evidence, request.acquired_evidence
                )
                return await self._providers.judge.judge_response(
                    {
                        "plant_name": identity.normalized_binomial,
                        "required_aspects": [item.value for item in request.required_aspects],
                        "evidence_sources": evidence_sources,
                        "local_answerability": (
                            request.local_answerability.as_metadata()
                            if request.local_answerability is not None
                            else None
                        ),
                    },
                    {
                        "passing_score": 1.0,
                        "criteria": [
                            "Use only the supplied evidence_sources entries and report direct source support per aspect.",
                            "Each source_support item must cite exactly one supplied source URL.",
                            "Return full, partial, insufficient, or contradictory.",
                            "Safety aspects require direct source-supported evidence.",
                        ],
                    },
                )

            local = await self._coverage.evaluate_local(
                required_aspects=required,
                retrieve=retrieve,
                judge=judge,
                thresholds=thresholds,
            )
            persistence = EnrichmentEvidencePersistenceService(
                repository,
                vector_index=vector_index,
                embedding_provider=self._providers.embeddings,
            )
            if not local.acquisition_aspects:
                await persistence.record_validation(
                    job_id=payload.run_id,
                    taxonomy_provenance_id=payload.taxonomy_provenance_id,
                    policy_version=policy.version,
                    required_aspects=[item.value for item in required],
                    covered_aspects=[item.value for item in required],
                    missing_aspects=[],
                    answerability_status="full",
                    judge_confidence=local.answerability.confidence,
                    validation_metadata={"acquisition_avoided": True},
                )
                return EnrichmentExecution(
                    required,
                    (),
                    acquisition_avoided=True,
                    local_covered_count=len(required),
                )

            trusted_sources = TrustedSourceValidator()
            acquisition = await OfflineEnrichmentAcquisitionService(
                search=self._providers.search,
                trusted_sources=trusted_sources,
            ).acquire(
                identity=identity,
                required_aspects=required,
                acquisition_aspects=tuple(local.acquisition_aspects),
                policy=policy,
            )
            acquired_evidence = SemanticEvidence(
                sources=tuple(
                    SemanticSourceEvidence(
                        text=page.evidence_text,
                        metadata=_page_metadata(page),
                    )
                    for page in acquisition.evidence
                ),
                eligible_validation_statuses=frozenset({"trusted"}),
            )
            final = await self._coverage.evaluate_final(
                local=local,
                acquired_evidence=acquired_evidence,
                judge=judge,
                thresholds=thresholds,
            )
            if final.answerability.status == "contradictory":
                covered: tuple[RequiredAspect, ...] = ()
            else:
                covered = tuple(
                    item for item in required if item in final.final_covered_aspects
                )
            missing = tuple(item for item in required if item not in covered)

            pages_by_url = {page.result.url: page for page in acquisition.evidence}
            allowed_aspects = {
                item.value
                for item in covered
                if item in local.acquisition_aspects
            }
            accepted_claims = _accepted_acquired_claims(
                final.answerability.source_support,
                pages_by_url=pages_by_url,
                allowed_aspects=allowed_aspects,
            )

            states: list[object] = []
            if final.answerability.status in {"full", "partial"}:
                for claim in accepted_claims:
                    state = await persistence.persist_claim_relational(
                        identity=identity,
                        taxonomy_provenance_id=payload.taxonomy_provenance_id,
                        claim=claim,
                    )
                    states.append(state)

            validation_id = await persistence.record_validation(
                job_id=payload.run_id,
                taxonomy_provenance_id=payload.taxonomy_provenance_id,
                policy_version=policy.version,
                required_aspects=[item.value for item in required],
                covered_aspects=[item.value for item in covered],
                missing_aspects=[item.value for item in missing],
                answerability_status=final.answerability.status,
                judge_confidence=final.answerability.confidence,
                validation_metadata={
                    "acquisition_avoided": False,
                    "search_count": len(acquisition.searched_groups),
                    "accepted_claim_count": len(accepted_claims),
                },
            )

            states_by_document_id = {
                state.document_id: state for state in states
            }
            for document_id in sorted(states_by_document_id):
                await persistence.associate_validation_and_refresh(
                    validation_id=validation_id,
                    document_id=document_id,
                )
            safety_rejected = any(
                item in policy.safety_sensitive_aspects
                and item in local.acquisition_aspects
                and item not in covered
                for item in required
            )
            return EnrichmentExecution(
                covered,
                missing,
                acquisition_avoided=False,
                safety_evidence_rejected=safety_rejected,
                local_covered_count=len(local.local_covered_aspects),
                search_count=len(acquisition.searched_groups),
                accepted_aspect_count=len(
                    {
                        aspect
                        for claim in accepted_claims
                        for aspect in claim.supported_aspects
                    }
                ),
            )


def _page_metadata(page: TrustedPageEvidence) -> dict[str, object]:
    return {
        "url": page.result.url,
        "domain": page.result.source_domain,
        "title": page.result.title,
        "validation_status": page.validation_status,
        "fetch_status": page.fetch_status,
    }


def _accepted_acquired_claims(
    support_items: list[dict[str, object]],
    *,
    pages_by_url: dict[str, TrustedPageEvidence],
    allowed_aspects: set[str],
) -> list[AcceptedEnrichmentClaim]:
    accepted: list[AcceptedEnrichmentClaim] = []
    now = datetime.now(UTC)
    for support in support_items:
        urls = support.get("source_urls")
        aspects = support.get("covered_aspects")
        if not isinstance(urls, list) or not isinstance(aspects, list):
            continue
        if len(urls) != 1:
            continue
        raw_url = urls[0]
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        url = raw_url.strip()
        if url not in pages_by_url:
            continue
        page = pages_by_url[url]
        if page.validation_status != "trusted":
            continue
        supported = tuple(
            dict.fromkeys(
                str(aspect) for aspect in aspects if str(aspect) in allowed_aspects
            )
        )
        claim = str(support.get("claim") or "").strip()
        quote = str(support.get("evidence_quote") or "").strip()
        if not supported or not claim or not quote:
            continue
        confidence = max(
            0.0,
            min(1.0, float(support.get("confidence") or 0.0)),
        )
        raw_version = (
            page.result.metadata.get("source_version")
            if isinstance(page.result.metadata, dict)
            else None
        )
        source_version = str(raw_version or "").strip() or hashlib.sha256(
            page.evidence_text.encode()
        ).hexdigest()
        accepted.append(
            AcceptedEnrichmentClaim(
                claim=claim,
                evidence_quote=quote,
                source_url=url,
                source_title=page.result.title,
                source_domain=(page.result.source_domain or urlparse(url).netloc),
                source_version=source_version,
                source_retrieved_at=now,
                source_published_at=None,
                supported_aspects=supported,
                confidence=confidence,
            )
        )
    return accepted


__all__ = [
    "MAX_JUDGE_EVIDENCE_CHARS",
    "MAX_JUDGE_SOURCES",
    "EnrichmentExecution",
    "EnrichmentExecutionService",
    "ProductionEnrichmentService",
    "_bounded_evidence_sources",
]
