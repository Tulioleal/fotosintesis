"""AssistantTools facade: orchestration over knowledge, providers, and repositories."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.assistant.repository import AssistantRepository
from app.assistant.tools.ingestion import (
    build_validated_claim_document,
)
from app.assistant.tools.trusted_sources import (
    is_external_fallback_selection,
    trusted_first_results,
)
from app.assistant.tools.types import (
    EXTERNAL_FALLBACK_VALIDATION_STATUS,
    ToolResult,
    build_assistant_failure_metadata,
)
from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence, TrustedPageEvidenceFetcher
from app.knowledge.plant_data import PlantDataLookupService, StructuredPlantEvidence
from app.knowledge.rag import KnowledgeVectorIndex
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeRetrievalFilters,
    ReviewStatus,
)
from app.providers.factory import ProviderRegistry, get_provider_registry
from app.providers.types import SearchResult


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
        canonical_species_key: str | None = None,
        accepted_gbif_key: int | None = None,
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
                canonical_species_key=canonical_species_key,
                accepted_gbif_key=accepted_gbif_key,
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

    async def trusted_web_search(
        self, query: str, *, candidates: list[SearchResult] | None = None
    ) -> ToolResult:
        try:
            results = candidates
            if results is None:
                results = await self.providers.search.search(
                    query,
                    allowed_domains=sorted(self.trusted_sources.approved_domains),
                )
            selected = trusted_first_results(results, self.trusted_sources)
            if is_external_fallback_selection(selected, self.trusted_sources):
                return ToolResult(
                    ok=True,
                    data=[
                        TrustedPageEvidence(
                            result=selected[0],
                            error="external fallback source",
                            validation_status=EXTERNAL_FALLBACK_VALIDATION_STATUS,
                            fetch_status="skipped",
                            fetch_error_category="external_fallback",
                            snippet_length=len(selected[0].snippet or ""),
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
            metadata = build_assistant_failure_metadata(exc)
            return ToolResult(ok=False, error=f"model_generate_text failed: {exc}", failure_metadata=metadata)
        return ToolResult(ok=True, data=result.text)

    async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
        try:
            result = await self.providers.model.generate_json(prompt, schema, **kwargs)
        except Exception as exc:
            metadata = build_assistant_failure_metadata(exc)
            return ToolResult(ok=False, error=f"model_generate_json failed: {exc}", failure_metadata=metadata)
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

    async def ingest_validated_claims(self, claims: list[dict[str, object]]) -> ToolResult:
        try:
            if not claims:
                return ToolResult(ok=True, data={"document_ids": []})
            index = KnowledgeVectorIndex(self.knowledge_repository)
            persisted_ids: list[str] = []
            for claim in claims:
                document = build_validated_claim_document(claim=claim)
                if document is None:
                    continue
                persisted = await index.ingest_document(document, embedding_provider=self.providers.embeddings)
                persisted_ids.append(str(persisted.id))
        except Exception as exc:
            await self.knowledge_repository.rollback()
            return ToolResult(ok=False, error=f"ingest_validated_claims failed: {exc}")
        return ToolResult(ok=True, data={"document_ids": persisted_ids})

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
