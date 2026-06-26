from __future__ import annotations

from uuid import UUID

from app.assistant.graph import answerability, answers, classifier, topology, web_evidence
from app.assistant.graph.plant_resolution import _normalize_plant_name, display_plant_name, operational_plant_name
from app.assistant.graph.types import AssistantState, FallbackResponseDraft
from app.assistant.tools import AssistantTools
from app.core.settings import Settings, get_settings
from app.knowledge.plant_data import StructuredPlantEvidence
from app.providers.fallback_context import clear_provider_fallbacks, get_provider_fallbacks


class AssistantGraph:
    def __init__(self, tools: AssistantTools, settings: Settings | None = None) -> None:
        self.tools = tools
        self.settings = settings or get_settings()
        self.graph = topology._compile_graph(self)

    async def run(
        self,
        *,
        user_id: UUID,
        message: str,
        plant_hint: str | None,
        plant_binomial_name: str | None = None,
        plant_scientific_name: str | None = None,
    ) -> AssistantState:
        state: AssistantState = {
            "user_id": user_id,
            "message": message.strip(),
            "plant_hint": _normalize_plant_name(plant_hint),
            "plant_binomial_name": _normalize_plant_name(plant_binomial_name),
            "plant_scientific_name": _normalize_plant_name(plant_scientific_name),
            "operational_plant_name": operational_plant_name(
                plant=plant_hint,
                plant_binomial_name=plant_binomial_name,
                plant_scientific_name=plant_scientific_name,
            ),
            "display_plant_name": display_plant_name(
                plant=plant_hint,
                plant_binomial_name=plant_binomial_name,
                plant_scientific_name=plant_scientific_name,
            ),
            "tool_failures": [],
            "sources": [],
            "fallback_reasons": [],
            "provider_fallbacks": [],
            "requires_confirmation": False,
        }
        clear_provider_fallbacks()
        result = await self.graph.ainvoke(state)
        provider_fallbacks = get_provider_fallbacks()
        if provider_fallbacks:
            result["provider_fallbacks"] = list(result.get("provider_fallbacks", [])) + provider_fallbacks
            result["fallback_reasons"] = list(result.get("fallback_reasons", []))
        return result

    async def classify_intent(self, state: AssistantState) -> dict:
        return await classifier.classify_intent(self, state)

    async def load_user_context(self, state: AssistantState) -> dict:
        return await answers.load_user_context(self, state)

    async def retrieve(self, state: AssistantState) -> dict:
        return await answers.retrieve(self, state)

    async def evaluate_sufficiency(self, state: AssistantState) -> dict:
        return await answerability.evaluate_sufficiency(self, state)

    async def fallback_web_search(self, state: AssistantState) -> dict:
        return await web_evidence.fallback_web_search(self, state)

    async def handle_action(self, state: AssistantState) -> dict:
        return await answers.handle_action(self, state)

    async def clarify(self, state: AssistantState) -> dict:
        return await answers.clarify(self, state)

    async def generate_answer(self, state: AssistantState) -> dict:
        return await answers.generate_answer(self, state)

    async def _generate_structured_answer(
        self, state: AssistantState, evidence: StructuredPlantEvidence
    ) -> dict:
        return await answers._generate_structured_answer(self, state, evidence)

    async def _generate_web_answer(self, state: AssistantState, web_results: list[object]) -> dict:
        return await answers._generate_web_answer(self, state, web_results)

    async def _generate_disclaimed_guidance(self, state: AssistantState) -> dict:
        return await answers._generate_disclaimed_guidance(self, state)

    async def _generate_grounded_answer(
        self,
        state: AssistantState,
        *,
        plant_name: str | None,
        evidence_type: str,
        evidence: str,
        limitations: list[str],
        source_metadata: list[dict],
        extra_context: str = "",
    ) -> dict:
        return await answers._generate_grounded_answer(
            self,
            state,
            plant_name=plant_name,
            evidence_type=evidence_type,
            evidence=evidence,
            limitations=limitations,
            source_metadata=source_metadata,
            extra_context=extra_context,
        )

    async def _generate_fallback_response(
        self, state: AssistantState | dict, draft: FallbackResponseDraft
    ) -> dict:
        return await answers._generate_fallback_response(self, state, draft)

    async def failure(self, state: AssistantState) -> dict:
        return await answers.failure(self, state)


__all__ = ["AssistantGraph"]
