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

    async def knowledge_search(self, *, scientific_name: str, topic: str) -> ToolResult:
        try:
            result = await KnowledgeAcquisitionService(
                self.knowledge_repository,
                providers=self.providers,
            ).retrieve_or_acquire(
                scientific_name=scientific_name,
                topic=topic,
                filters=KnowledgeRetrievalFilters(
                    scientific_name=scientific_name,
                    topic=topic,
                    review_status=ReviewStatus.auto_ingested,
                ),
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"knowledge_search failed: {exc}")
        return ToolResult(ok=True, data=result)

    async def trusted_web_search(self, query: str) -> ToolResult:
        try:
            results = await self.providers.search.search(
                query,
                allowed_domains=sorted(self.trusted_sources.approved_domains),
            )
            return ToolResult(ok=True, data=await self.page_evidence_fetcher.fetch_all(results))
        except Exception as exc:
            return ToolResult(ok=False, error=f"trusted_web_search failed: {exc}")

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
            return f"plant_data_lookup ingestion failed: {exc}"
        return None

    async def ingest_web_evidence(
        self,
        *,
        scientific_name: str,
        topic: str,
        results: list[SearchResult | TrustedPageEvidence],
    ) -> ToolResult:
        try:
            if not results:
                return ToolResult(ok=False, error="ingest_web_evidence failed: no results")
            trusted_evidence = _trusted_page_evidence(results, self.trusted_sources)
            if not trusted_evidence:
                return ToolResult(
                    ok=False,
                    error="ingest_web_evidence failed: no trusted results",
                )
            now = datetime.now(timezone.utc)
            document = KnowledgeDocumentInput(
                scientific_name=scientific_name,
                topic=topic,
                title=f"{scientific_name}: {topic} web fallback evidence",
                content=_web_evidence_content(scientific_name, topic, trusted_evidence),
                confidence=0.55,
                review_status=ReviewStatus.auto_ingested,
                sources=[
                    KnowledgeSourceInput(
                        title=evidence.result.title,
                        url=evidence.result.url,
                        source_domain=evidence.result.source_domain,
                        retrieved_at=now,
                    )
                    for evidence in trusted_evidence
                ],
            )
            persisted = await KnowledgeVectorIndex(self.knowledge_repository).ingest_document(
                document,
                embedding_provider=self.providers.embeddings,
            )
        except Exception as exc:
            return ToolResult(ok=False, error=f"ingest_web_evidence failed: {exc}")
        return ToolResult(ok=True, data={"document_id": str(persisted.id)})

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


def _trusted_page_evidence(
    results: list[SearchResult | TrustedPageEvidence], trusted_sources: TrustedSourceValidator
) -> list[TrustedPageEvidence]:
    evidence_items: list[TrustedPageEvidence] = []
    for item in results:
        evidence = item if isinstance(item, TrustedPageEvidence) else TrustedPageEvidence(result=item)
        if trusted_sources.is_trusted(evidence.result):
            evidence_items.append(evidence)
    return evidence_items
