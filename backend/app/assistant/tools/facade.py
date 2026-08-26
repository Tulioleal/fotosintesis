"""AssistantTools facade: orchestration over knowledge, providers, and repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
        knowledge_runtime: Any | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge_repository = knowledge_repository
        self.providers = providers or get_provider_registry()
        self.trusted_sources = trusted_sources or TrustedSourceValidator()
        self.page_evidence_fetcher = page_evidence_fetcher or TrustedPageEvidenceFetcher(
            self.trusted_sources
        )
        self.knowledge_runtime = knowledge_runtime
        self.tool_calls: list[dict[str, object]] = []

    def _record_tool_call(self, name: str, result: ToolResult) -> None:
        """Append a bounded tool record (name, success, bounded error category).

        Tool arguments, retrieved document bodies, and provider internals are
        never captured here.
        """
        error_category: str | None = None
        if not result.ok:
            if result.failure_metadata is not None:
                error_category = result.failure_metadata.failure_category
            else:
                error_category = "tool_error"
        self.tool_calls.append(
            {"name": name, "success": result.ok, "error_category": error_category}
        )

    def _acquisition_service(self) -> KnowledgeAcquisitionService:
        if self.knowledge_runtime is not None:
            index = KnowledgeVectorIndex(
                self.knowledge_repository, runtime=self.knowledge_runtime
            )
            return KnowledgeAcquisitionService(
                self.knowledge_repository,
                providers=self.providers,
                vector_index=index,
            )
        return KnowledgeAcquisitionService(
            self.knowledge_repository,
            providers=self.providers,
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
            result = await self._acquisition_service().retrieve_or_acquire(
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
            result = ToolResult(ok=False, error=f"knowledge_search failed: {exc}")
            self._record_tool_call("knowledge_search", result)
            return result
        result = ToolResult(ok=True, data=result)
        self._record_tool_call("knowledge_search", result)
        return result

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
                result = ToolResult(
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
                self._record_tool_call("trusted_web_search", result)
                return result
            result = ToolResult(ok=True, data=await self.page_evidence_fetcher.fetch_all(selected))
            self._record_tool_call("trusted_web_search", result)
            return result
        except Exception as exc:
            result = ToolResult(ok=False, error=f"trusted_web_search failed: {exc}")
            self._record_tool_call("trusted_web_search", result)
            return result

    async def generate_text(self, prompt: str) -> ToolResult:
        try:
            result = await self.providers.model.generate_text(prompt)
        except Exception as exc:
            metadata = build_assistant_failure_metadata(exc)
            result = ToolResult(ok=False, error=f"model_generate_text failed: {exc}", failure_metadata=metadata)
            self._record_tool_call("generate_text", result)
            return result
        result = ToolResult(ok=True, data=result.text)
        self._record_tool_call("generate_text", result)
        return result

    async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
        try:
            result = await self.providers.model.generate_json(prompt, schema, **kwargs)
        except Exception as exc:
            metadata = build_assistant_failure_metadata(exc)
            result = ToolResult(ok=False, error=f"model_generate_json failed: {exc}", failure_metadata=metadata)
            self._record_tool_call("generate_json", result)
            return result
        result = ToolResult(ok=True, data=result.data)
        self._record_tool_call("generate_json", result)
        return result

    async def plant_data_lookup(self, *, scientific_name: str, topic: str) -> ToolResult:
        try:
            evidence = await PlantDataLookupService(
                trefle=self.providers.trefle,
                perenual=self.providers.perenual,
            ).lookup(scientific_name=scientific_name, topic=topic)
            if not evidence:
                result = ToolResult(ok=True, data=None)
                self._record_tool_call("plant_data_lookup", result)
                return result
            ingestion_error = await self._ingest_structured_evidence(evidence)
            result = ToolResult(
                ok=True,
                data={"evidence": evidence, "ingestion_error": ingestion_error},
            )
            self._record_tool_call("plant_data_lookup", result)
            return result
        except Exception as exc:
            result = ToolResult(ok=False, error=f"plant_data_lookup failed: {exc}")
            self._record_tool_call("plant_data_lookup", result)
            return result

    async def _ingest_structured_evidence(
        self, evidence: StructuredPlantEvidence
    ) -> str | None:
        try:
            index = KnowledgeVectorIndex(
                self.knowledge_repository, runtime=self.knowledge_runtime
            ) if self.knowledge_runtime is not None else KnowledgeVectorIndex(self.knowledge_repository)
            await index.ingest_document(
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
                result = ToolResult(ok=True, data={"document_ids": []})
                self._record_tool_call("ingest_validated_claims", result)
                return result
            index = KnowledgeVectorIndex(
                self.knowledge_repository, runtime=self.knowledge_runtime
            ) if self.knowledge_runtime is not None else KnowledgeVectorIndex(self.knowledge_repository)
            persisted_ids: list[str] = []
            for claim in claims:
                document = build_validated_claim_document(claim=claim)
                if document is None:
                    continue
                persisted = await index.ingest_document(document, embedding_provider=self.providers.embeddings)
                persisted_ids.append(str(persisted.id))
        except Exception as exc:
            await self.knowledge_repository.rollback()
            result = ToolResult(ok=False, error=f"ingest_validated_claims failed: {exc}")
            self._record_tool_call("ingest_validated_claims", result)
            return result
        result = ToolResult(ok=True, data={"document_ids": persisted_ids})
        self._record_tool_call("ingest_validated_claims", result)
        return result

    async def garden_lookup(self, *, user_id: UUID) -> ToolResult:
        try:
            result = ToolResult(ok=True, data=await self.repository.list_garden(user_id=user_id))
        except Exception as exc:
            result = ToolResult(ok=False, error=f"garden_lookup failed: {exc}")
        self._record_tool_call("garden_lookup", result)
        return result

    async def reminder_create(
        self,
        *,
        user_id: UUID,
        garden_plant_id: UUID,
        action: str,
        due_at: datetime,
        recurrence: str | None,
        justification: str | None,
        timezone: str | None = None,
    ) -> ToolResult:
        try:
            from app.reminders.repository import ReminderRepository
            from app.reminders.validation import (
                MissingReminderTimezoneError,
                ReminderValidationError,
                ensure_future_due,
                resolve_effective_timezone,
            )
            from app.schemas.reminders import ReminderCreate as ReminderCreatePayload
            from app.schemas.reminders import ReminderRecurrence

            recurrence_value = (recurrence or "none").strip().lower()
            try:
                recurrence_enum = ReminderRecurrence(recurrence_value)
            except ValueError:
                raise ReminderValidationError(
                    "State a recurrence of none, daily, weekly or monthly."
                ) from None

            zone = resolve_effective_timezone(
                override=timezone,
                user_timezone=await self._stored_user_timezone(user_id),
            )
            if due_at.tzinfo is not None:
                local_due = due_at.astimezone(zone)
            else:
                local_due = due_at.replace(tzinfo=None)
            due_at_utc = ensure_future_due(
                due_date=local_due.date(), due_time=local_due.time(), zone=zone
            )

            repository = ReminderRepository(self.repository.session)
            existing = await repository.find_equivalent(
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at_utc,
                recurrence=recurrence_enum.value,
            )
            if existing is not None:
                result = ToolResult(
                    ok=True,
                    data={"id": str(existing), "duplicate": True},
                )
                self._record_tool_call("reminder_create", result)
                return result

            reminder = await repository.create_reminder(
                user_id=user_id,
                payload=ReminderCreatePayload(
                    garden_plant_id=garden_plant_id,
                    action=action,
                    date=local_due.date(),
                    time=local_due.time(),
                    recurrence=recurrence_enum,
                    suggestion_justification=justification,
                    timezone=zone.key,
                ),
            )
            if reminder is None:
                raise ReminderValidationError(
                    "The selected plant does not exist in your garden."
                )
            result = ToolResult(ok=True, data={"id": str(reminder.id)})
        except (
            ReminderValidationError,
            MissingReminderTimezoneError,
        ) as validation_error:
            result = ToolResult(ok=False, error=str(validation_error))
            self._record_tool_call("reminder_create", result)
            return result
        except Exception as exc:
            result = ToolResult(ok=False, error=f"reminder_create failed: {exc}")
            self._record_tool_call("reminder_create", result)
            return result
        self._record_tool_call("reminder_create", result)
        return result

    async def _stored_user_timezone(self, user_id: UUID) -> str | None:
        """Best-effort stored user timezone for effective-zone resolution."""
        try:
            from sqlalchemy import select

            from app.auth.tables import users

            row = (
                await self.repository.session.execute(
                    select(users.c.timezone).where(users.c.id == user_id)
                )
            ).first()
            return row[0] if row else None
        except Exception:
            return None

    async def light_measurement_lookup(
        self, *, user_id: UUID, garden_plant_id: UUID | None = None
    ) -> ToolResult:
        try:
            result = ToolResult(
                ok=True,
                data=await self.repository.latest_light_measurement(
                    user_id=user_id, garden_plant_id=garden_plant_id
                ),
            )
        except Exception as exc:
            result = ToolResult(ok=False, error=f"light_measurement_lookup failed: {exc}")
        self._record_tool_call("light_measurement_lookup", result)
        return result
