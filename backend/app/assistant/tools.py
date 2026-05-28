from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.assistant.repository import AssistantRepository
from app.identification.gbif import GbifClient
from app.knowledge.acquisition import KnowledgeAcquisitionService
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import KnowledgeRetrievalFilters, ReviewStatus
from app.providers.factory import ProviderRegistry, get_provider_registry


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
    ) -> None:
        self.repository = repository
        self.knowledge_repository = knowledge_repository
        self.providers = providers or get_provider_registry()

    async def knowledge_search(self, *, scientific_name: str, topic: str) -> ToolResult:
        try:
            result = await KnowledgeAcquisitionService(self.knowledge_repository).retrieve_or_acquire(
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
            return ToolResult(ok=True, data=await self.providers.search.search(query))
        except Exception as exc:
            return ToolResult(ok=False, error=f"trusted_web_search failed: {exc}")

    async def taxonomy_validate(self, scientific_name: str) -> ToolResult:
        try:
            return ToolResult(ok=True, data=await GbifClient().match_name(scientific_name))
        except Exception as exc:
            return ToolResult(ok=False, error=f"taxonomy_validate failed: {exc}")

    async def ingestion(self, *, scientific_name: str, topic: str) -> ToolResult:
        return await self.knowledge_search(scientific_name=scientific_name, topic=topic)

    async def embeddings(self, text: str) -> ToolResult:
        try:
            return ToolResult(ok=True, data=await self.providers.embeddings.create_embeddings([text]))
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
