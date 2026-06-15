from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.assistant.repository import AssistantRepository
from app.identification.gbif import GbifClient
from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence, TrustedPageEvidenceFetcher
from app.knowledge.plant_data import PlantDataLookupService, StructuredPlantEvidence
from app.knowledge.rag import KnowledgeVectorIndex
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.factory import ProviderRegistry, get_provider_registry
from app.providers.types import SearchResult


TRUSTED_WEB_EVIDENCE_CONFIDENCE = 0.55
EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE = 0.35
EXTERNAL_FALLBACK_VALIDATION_STATUS = "external_fallback"


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: object | None = None
    error: str | None = None


class AssistantTools:
    def __init__(
        self,
        repository: AssistantRepository,
        knowledge_repository: KnowledgeRepository,
        *,
        providers: ProviderRegistry | None = None,
        trusted_sources: TrustedSourceValidator | None = None,
        page_evidence_fetcher: TrustedPageEvidenceFetcher | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge_repository = knowledge_repository
        self.providers = providers or get_provider_registry()
        self.trusted_sources = trusted_sources or TrustedSourceValidator()
        self.page_evidence_fetcher = page_evidence_fetcher or TrustedPageEvidenceFetcher(
            self.trusted_sources
        )

    async def knowledge_search(
        self,
        *,
        scientific_name: str,
        topic: str,
        required_aspects: list[str] | None = None,
        question: str | None = None,
    ) -> ToolResult:
        try:
            result = await KnowledgeAcquisitionService(
                self.knowledge_repository,
                providers=self.providers,
            ).retrieve_or_acquire(
                scientific_name=scientific_name,
                topic=topic,
                required_aspects=required_aspects or [],
                question=question,
                filters=KnowledgeRetrievalFilters(
                    scientific_name=scientific_name,
                    topic=topic,
                    review_status=ReviewStatus.auto_ingested,
                ),
            )
        except Exception as exc:
            await self.knowledge_repository.rollback()
            return ToolResult(ok=False, error=f"knowledge_search failed: {exc}")
        return ToolResult(ok=True, data=result)

    async def trusted_web_search(self, query: str) -> ToolResult:
        try:
            results = await self.providers.search.search(
                query,
                allowed_domains=sorted(self.trusted_sources.approved_domains),
            )
            selected = _trusted_first_results(results, self.trusted_sources)
            if _is_external_fallback_selection(selected, self.trusted_sources):
                return ToolResult(
                    ok=True,
                    data=[
                        TrustedPageEvidence(
                            result=selected[0],
                            error="external fallback source",
                            validation_status=EXTERNAL_FALLBACK_VALIDATION_STATUS,
                        )
                    ],
                )
            return ToolResult(ok=True, data=await self.page_evidence_fetcher.fetch_all(selected))
        except Exception as exc:
            return ToolResult(ok=False, error=f"trusted_web_search failed: {exc}")

    async def generate_text(self, prompt: str) -> ToolResult:
        try:
            result = await self.providers.model.generate_text(prompt)
        except Exception as exc:
            return ToolResult(ok=False, error=f"model_generate_text failed: {exc}")
        return ToolResult(ok=True, data=result.text)

    async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
        try:
            result = await self.providers.model.generate_json(prompt, schema, **kwargs)
        except Exception as exc:
            return ToolResult(ok=False, error=f"model_generate_json failed: {exc}")
        return ToolResult(ok=True, data=result.data)

    async def plant_data_lookup(self, *, scientific_name: str, topic: str) -> ToolResult:
        try:
            evidence = await PlantDataLookupService(
                trefle=self.providers.trefle,
                perenual=self.providers.perenual,
            ).lookup(scientific_name=scientific_name, topic=topic)
            if not evidence:
                return ToolResult(ok=True, data=None)
            ingestion_error = await self._ingest_structured_evidence(evidence)
            return ToolResult(
                ok=True,
                data={"evidence": evidence, "ingestion_error": ingestion_error},
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"plant_data_lookup failed: {exc}")

    async def _ingest_structured_evidence(
        self, evidence: StructuredPlantEvidence
    ) -> str | None:
        try:
            await KnowledgeVectorIndex(self.knowledge_repository).ingest_document(
                evidence.to_document(),
                embedding_provider=self.providers.embeddings,
            )
        except Exception as exc:
            await self.knowledge_repository.rollback()
            return f"plant_data_lookup ingestion failed: {exc}"
        return None

    async def ingest_web_evidence(
        self,
        *,
        scientific_name: str,
        topic: str,
        results: list[SearchResult | TrustedPageEvidence],
        metadata: dict[str, object] | None = None,
    ) -> ToolResult:
        try:
            if not results:
                return ToolResult(ok=False, error="ingest_web_evidence failed: no results")
            evidence_items = _persistable_page_evidence(results, self.trusted_sources)
            if not evidence_items:
                return ToolResult(
                    ok=False,
                    error="ingest_web_evidence failed: no trusted results",
                )
            metadata = metadata or {}
            if not metadata.get("covered_aspects"):
                return ToolResult(
                    ok=False,
                    error="ingest_web_evidence failed: no validated covered aspects",
                )
            if len(evidence_items) > 1 and not metadata.get("source_validations"):
                return ToolResult(
                    ok=False,
                    error="ingest_web_evidence failed: source validations required for multiple results",
                )
            index = KnowledgeVectorIndex(self.knowledge_repository)
            persisted_ids: list[str] = []
            for item in evidence_items:
                now = datetime.now(timezone.utc)
                document = KnowledgeDocumentInput(
                    scientific_name=scientific_name,
                    topic=topic,
                    title=f"{scientific_name}: {topic} web fallback evidence",
                    content=_web_evidence_content(scientific_name, topic, [item]),
                    confidence=_web_evidence_confidence([item]),
                    review_status=ReviewStatus.auto_ingested,
                    metadata=_metadata_for_source(metadata, item),
                    sources=[
                        KnowledgeSourceInput(
                            title=item.result.title,
                            url=item.result.url,
                            source_domain=item.result.source_domain,
                            retrieved_at=now,
                            validation_status=item.validation_status,
                        )
                    ],
                )
                persisted = await index.ingest_document(
                    document,
                    embedding_provider=self.providers.embeddings,
                )
                persisted_ids.append(str(persisted.id))
        except Exception as exc:
            await self.knowledge_repository.rollback()
            return ToolResult(ok=False, error=f"ingest_web_evidence failed: {exc}")
        return ToolResult(ok=True, data={"document_id": persisted_ids[0], "document_ids": persisted_ids})

    async def ingest_validated_claims(self, claims: list[dict[str, object]]) -> ToolResult:
        try:
            if not claims:
                return ToolResult(ok=True, data={"document_ids": []})
            index = KnowledgeVectorIndex(self.knowledge_repository)
            persisted_ids: list[str] = []
            for claim in claims:
                now = datetime.now(timezone.utc)
                source_url = str(claim.get("source_url") or "")
                if not source_url:
                    continue
                confidence = float(claim.get("confidence") or TRUSTED_WEB_EVIDENCE_CONFIDENCE)
                metadata = {
                    "topic": claim.get("topic"),
                    "required_aspects": list(claim.get("required_aspects") or []),
                    "covered_aspects": list(claim.get("covered_aspects") or []),
                    "missing_aspects": list(claim.get("missing_aspects") or []),
                    "language": claim.get("language") or "es",
                    "evidence_type": "validated_web_claim",
                    "answerability_status": claim.get("answerability_status"),
                    "validation_confidence": confidence,
                    "source_support_claim": claim.get("claim"),
                    "source_support_quote": claim.get("evidence_quote"),
                    "persisted_from": "assistant_final_judge",
                    "source_domain": claim.get("source_domain"),
                }
                document = KnowledgeDocumentInput(
                    scientific_name=str(claim.get("scientific_name") or ""),
                    topic=str(claim.get("topic") or "care"),
                    title=f"{claim.get('scientific_name')}: validated web claim",
                    content=_validated_claim_content(claim),
                    confidence=confidence,
                    review_status=ReviewStatus.auto_ingested,
                    metadata=metadata,
                    sources=[
                        KnowledgeSourceInput(
                            title=str(claim.get("source_title") or claim.get("source_domain") or source_url),
                            url=source_url,
                            source_domain=str(claim.get("source_domain") or ""),
                            retrieved_at=now,
                            validation_status=str(claim.get("answerability_status") or "validated"),
                        )
                    ],
                )
                persisted = await index.ingest_document(document, embedding_provider=self.providers.embeddings)
                persisted_ids.append(str(persisted.id))
        except Exception as exc:
            await self.knowledge_repository.rollback()
            return ToolResult(ok=False, error=f"ingest_validated_claims failed: {exc}")
        return ToolResult(ok=True, data={"document_ids": persisted_ids})

    async def taxonomy_validate(self, scientific_name: str) -> ToolResult:
        try:
            return ToolResult(ok=True, data=await GbifClient().match_name(scientific_name))
        except Exception as exc:
            return ToolResult(ok=False, error=f"taxonomy_validate failed: {exc}")

    async def ingestion(self, *, scientific_name: str, topic: str) -> ToolResult:
        return await self.knowledge_search(scientific_name=scientific_name, topic=topic)

    async def embeddings(self, text: str) -> ToolResult:
        try:
            return ToolResult(
                ok=True, data=await self.providers.embeddings.create_embeddings([text])
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"embeddings failed: {exc}")

    async def garden_lookup(self, *, user_id: UUID) -> ToolResult:
        try:
            return ToolResult(ok=True, data=await self.repository.list_garden(user_id=user_id))
        except Exception as exc:
            return ToolResult(ok=False, error=f"garden_lookup failed: {exc}")

    async def reminder_create(
        self,
        *,
        user_id: UUID,
        garden_plant_id: UUID,
        action: str,
        due_at: datetime,
        recurrence: str | None,
        justification: str | None,
    ) -> ToolResult:
        try:
            reminder_id = await self.repository.create_reminder(
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at,
                recurrence=recurrence,
                justification=justification,
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"reminder_create failed: {exc}")
        return ToolResult(ok=True, data={"id": str(reminder_id)})

    async def light_measurement_lookup(
        self, *, user_id: UUID, garden_plant_id: UUID | None = None
    ) -> ToolResult:
        try:
            return ToolResult(
                ok=True,
                data=await self.repository.latest_light_measurement(
                    user_id=user_id, garden_plant_id=garden_plant_id
                ),
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"light_measurement_lookup failed: {exc}")


def _web_evidence_content(
    scientific_name: str, topic: str, evidence_items: list[TrustedPageEvidence]
) -> str:
    evidence = " ".join(
        f"{item.result.title}: {item.evidence_text} Source: {item.result.url}."
        for item in evidence_items
    )
    return f"Live web fallback evidence for {scientific_name} about {topic}. {evidence}"


def _validated_claim_content(claim: dict[str, object]) -> str:
    aspects = ", ".join(str(aspect) for aspect in claim.get("covered_aspects") or [])
    return (
        f"Validated evidence for {claim.get('scientific_name')}. "
        f"Topic: {claim.get('topic')}. Covered aspects: {aspects}. "
        f"Claim: {claim.get('claim')}. Evidence quote: {claim.get('evidence_quote')}. "
        f"Source: {claim.get('source_url')}. Validation confidence: {claim.get('confidence')}."
    )


def _metadata_for_source(metadata: dict[str, object], item: TrustedPageEvidence) -> dict[str, object]:
    source_metadata = dict(metadata)
    validations = metadata.get("source_validations")
    if isinstance(validations, list):
        for validation in validations:
            if not isinstance(validation, dict) or validation.get("url") != item.result.url:
                continue
            source_metadata["covered_aspects"] = list(validation.get("covered_aspects", []))
            source_metadata["validation_confidence"] = validation.get("validation_confidence", 0.0)
            break
    source_metadata.pop("source_validations", None)
    source_metadata["source_domain"] = item.result.source_domain
    return source_metadata


def _trusted_first_results(
    results: list[SearchResult], trusted_sources: TrustedSourceValidator
) -> list[SearchResult]:
    trusted = trusted_sources.filter(results)
    if trusted:
        return trusted
    return results[:1]


def _is_external_fallback_selection(
    results: list[SearchResult], trusted_sources: TrustedSourceValidator
) -> bool:
    return bool(results) and not trusted_sources.is_trusted(results[0])


def _persistable_page_evidence(
    results: list[SearchResult | TrustedPageEvidence], trusted_sources: TrustedSourceValidator
) -> list[TrustedPageEvidence]:
    trusted_items: list[TrustedPageEvidence] = []
    external_fallback_items: list[TrustedPageEvidence] = []
    for item in results:
        evidence = item if isinstance(item, TrustedPageEvidence) else TrustedPageEvidence(result=item)
        if trusted_sources.is_trusted(evidence.result):
            trusted_items.append(evidence)
        elif evidence.validation_status == EXTERNAL_FALLBACK_VALIDATION_STATUS:
            external_fallback_items.append(evidence)
    return trusted_items or external_fallback_items[:1]


def _web_evidence_confidence(evidence_items: list[TrustedPageEvidence]) -> float:
    if all(
        evidence.validation_status == EXTERNAL_FALLBACK_VALIDATION_STATUS
        for evidence in evidence_items
    ):
        return EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE
    return TRUSTED_WEB_EVIDENCE_CONFIDENCE
