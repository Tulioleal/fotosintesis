from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
from uuid import UUID

from app.assistant.tools import AssistantTools, ToolResult
from app.knowledge.schemas import AcquisitionStatus, KnowledgeAcquisitionResult, KnowledgeChunk

BOTANICAL_TERMS = {
    "agua",
    "regar",
    "riego",
    "luz",
    "sol",
    "sombra",
    "hoja",
    "planta",
    "sustrato",
    "fertilizante",
    "plaga",
    "hongo",
    "poda",
    "flor",
    "raiz",
    "maceta",
    "plant",
    "watering",
    "light",
    "soil",
    "pest",
    "prune",
}
INJECTION_PATTERNS = (
    "ignore previous",
    "ignora las instrucciones",
    "system prompt",
    "developer message",
    "reveal your prompt",
    "omite las reglas",
)


class AssistantState(TypedDict, total=False):
    user_id: UUID
    message: str
    plant_hint: str | None
    intent: str
    topic: str
    garden: list[dict]
    selected_plant: dict | None
    ambiguous: bool
    out_of_domain: bool
    unsafe: bool
    retrieval: KnowledgeAcquisitionResult | None
    sufficient: bool
    sources: list[dict]
    answer: str
    requires_confirmation: bool
    reminder_suggestion: dict
    tool_failures: list[str]


class AssistantGraph:
    def __init__(self, tools: AssistantTools) -> None:
        self.tools = tools
        self.graph = _compile_graph(self)

    async def run(self, *, user_id: UUID, message: str, plant_hint: str | None) -> AssistantState:
        state: AssistantState = {
            "user_id": user_id,
            "message": message.strip(),
            "plant_hint": plant_hint,
            "tool_failures": [],
            "sources": [],
            "requires_confirmation": False,
        }
        return await self.graph.ainvoke(state)

    async def classify_intent(self, state: AssistantState) -> dict:
        message = state["message"].casefold()
        unsafe = any(pattern in message for pattern in INJECTION_PATTERNS)
        reminder = any(word in message for word in ("recordatorio", "recordame", "reminder"))
        light = "luz" in message or "light" in message
        botanical = any(term in message for term in BOTANICAL_TERMS) or bool(state.get("plant_hint"))
        intent = "reminder" if reminder else "light" if light else "botanical" if botanical else "out_of_domain"
        return {
            "intent": intent,
            "topic": _topic_for_message(message),
            "unsafe": unsafe,
            "out_of_domain": intent == "out_of_domain",
        }

    async def load_user_context(self, state: AssistantState) -> dict:
        result = await self.tools.garden_lookup(user_id=state["user_id"])
        if not result.ok:
            return {"tool_failures": state.get("tool_failures", []) + [result.error or "garden_lookup failed"], "garden": []}
        garden = list(result.data or [])
        selected, ambiguous = _select_plant(garden, state.get("plant_hint"), state["message"])
        return {"garden": garden, "selected_plant": selected, "ambiguous": ambiguous}

    async def retrieve(self, state: AssistantState) -> dict:
        if state.get("out_of_domain") or state.get("unsafe") or state.get("ambiguous"):
            return {}
        selected = state.get("selected_plant")
        scientific_name = selected.get("scientific_name") if selected else state.get("plant_hint")
        if not scientific_name:
            return {}
        result = await self.tools.knowledge_search(
            scientific_name=scientific_name,
            topic=state.get("topic") or "care",
        )
        if not result.ok:
            return {"tool_failures": state.get("tool_failures", []) + [result.error or "knowledge_search failed"]}
        retrieval = result.data
        return {"retrieval": retrieval, "sources": _sources_from_retrieval(retrieval)}

    async def evaluate_sufficiency(self, state: AssistantState) -> dict:
        retrieval = state.get("retrieval")
        chunks = getattr(retrieval, "chunks", []) if retrieval else []
        sufficient = bool(chunks) and max((chunk.confidence for chunk in chunks), default=0) >= 0.5
        return {"sufficient": sufficient}

    async def handle_action(self, state: AssistantState) -> dict:
        if state.get("unsafe") or state.get("out_of_domain") or state.get("ambiguous"):
            return {}
        if state.get("intent") == "light":
            selected = state.get("selected_plant")
            if not selected or selected.get("id") is None:
                return {"answer": "Necesito que indiques una planta guardada de tu jardin para consultar su medicion de luz."}
            result = await self.tools.light_measurement_lookup(
                user_id=state["user_id"],
                garden_plant_id=selected.get("id"),
            )
            if not result.ok:
                return {"tool_failures": state.get("tool_failures", []) + [result.error or "light lookup failed"]}
            if not result.data:
                return {"answer": "No encontre mediciones de luz guardadas para esa planta. Podes medir luz desde la seccion Luz."}
        if state.get("intent") == "reminder":
            return await self._handle_reminder(state)
        return {}

    async def _handle_reminder(self, state: AssistantState) -> dict:
        selected = state.get("selected_plant")
        missing = []
        if not selected or selected.get("id") is None:
            missing.append("planta")
        due_at = _extract_due_at(state["message"])
        if due_at is None:
            missing.append("fecha u hora")
        action = _extract_reminder_action(state["message"])
        if not action:
            missing.append("accion")
        recurrence = _extract_recurrence(state["message"])
        if recurrence is None:
            missing.append("recurrencia")
        if missing:
            return {
                "requires_confirmation": True,
                "answer": "Para crear el recordatorio necesito: " + ", ".join(missing) + ".",
            }
        justification = "Sugerido por el asistente desde la conversacion. Requiere confirmacion antes de crearse."
        if _wants_reminder_suggestion(state["message"]):
            return {
                "requires_confirmation": True,
                "reminder_suggestion": {
                    "garden_plant_id": selected["id"],
                    "plant_name": _display_plant(selected),
                    "action": action,
                    "due_at": due_at,
                    "recurrence": recurrence,
                    "suggestion_justification": justification,
                },
                "answer": "Tengo una sugerencia de recordatorio lista para confirmar antes de crearla.",
            }
        result = await self.tools.reminder_create(
            user_id=state["user_id"],
            garden_plant_id=selected["id"],
            action=action,
            due_at=due_at,
            recurrence=recurrence,
            justification="Creado por solicitud explicita en el asistente.",
        )
        if not result.ok:
            return {
                "tool_failures": state.get("tool_failures", []) + [result.error or "reminder_create failed"],
                "answer": "No pude crear el recordatorio. La accion no fue completada.",
            }
        return {"answer": f"Listo: cree el recordatorio para {selected['scientific_name']}."}

    async def clarify(self, state: AssistantState) -> dict:
        if state.get("unsafe"):
            return {"answer": "No puedo seguir instrucciones que intenten cambiar mis reglas o activar herramientas sin permiso."}
        if state.get("out_of_domain"):
            return {"answer": "Puedo ayudarte con cuidado de plantas, identificacion, luz, recordatorios y tu jardin. Reformula la pregunta dentro de ese tema."}
        if state.get("ambiguous"):
            names = ", ".join(_display_plant(plant) for plant in state.get("garden", [])[:5])
            return {"answer": f"¿Sobre cual planta queres consultar? En tu jardin veo: {names}."}
        if not state.get("selected_plant") and not state.get("plant_hint"):
            return {"answer": "Necesito saber de que planta hablamos. Indica el nombre o elegi una planta de tu jardin."}
        return {"answer": "No tengo evidencia suficiente para responder con seguridad. Puedo intentar buscar fuentes confiables o pedir mas detalles."}

    async def generate_answer(self, state: AssistantState) -> dict:
        if state.get("answer"):
            return {}
        retrieval = state.get("retrieval")
        chunks = getattr(retrieval, "chunks", []) if retrieval else []
        limitations = list(getattr(retrieval, "limitations", []) if retrieval else [])
        if not chunks:
            return await self.clarify(state)
        evidence = " ".join(_shorten(chunk.content, 280) for chunk in chunks[:3])
        selected = state.get("selected_plant")
        plant_name = selected.get("scientific_name") if selected else state.get("plant_hint")
        uncertainty = ""
        if getattr(retrieval, "status", None) == AcquisitionStatus.degraded or limitations:
            uncertainty = " La evidencia es limitada: " + " ".join(limitations)
        answer = (
            f"Para {plant_name}, la evidencia recuperada indica: {evidence}"
            f"{uncertainty} Evito afirmar detalles que no esten respaldados por esas fuentes."
        )
        return {"answer": answer}

    async def failure(self, state: AssistantState) -> dict:
        failures = state.get("tool_failures", [])
        if not failures:
            return {}
        if state.get("answer"):
            return {}
        return {"answer": "No pude completar la accion solicitada porque fallo una herramienta. No se realizo ningun cambio."}


def _compile_graph(owner: AssistantGraph):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _SequentialGraph(owner)

    graph = StateGraph(AssistantState)
    graph.add_node("classify_intent", owner.classify_intent)
    graph.add_node("load_user_context", owner.load_user_context)
    graph.add_node("retrieve", owner.retrieve)
    graph.add_node("evaluate_sufficiency", owner.evaluate_sufficiency)
    graph.add_node("handle_action", owner.handle_action)
    graph.add_node("generate_answer", owner.generate_answer)
    graph.add_node("clarify", owner.clarify)
    graph.add_node("failure", owner.failure)
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "load_user_context")
    graph.add_conditional_edges("load_user_context", _route_after_context, {"clarify": "clarify", "retrieve": "retrieve", "action": "handle_action"})
    graph.add_edge("retrieve", "evaluate_sufficiency")
    graph.add_conditional_edges("evaluate_sufficiency", _route_after_sufficiency, {"answer": "generate_answer", "clarify": "clarify"})
    graph.add_edge("handle_action", "failure")
    graph.add_conditional_edges("failure", _route_after_failure, {"answer": "generate_answer", "end": END})
    graph.add_edge("generate_answer", END)
    graph.add_edge("clarify", END)
    return graph.compile()


class _SequentialGraph:
    def __init__(self, owner: AssistantGraph) -> None:
        self.owner = owner

    async def ainvoke(self, state: AssistantState) -> AssistantState:
        for node in (self.owner.classify_intent, self.owner.load_user_context):
            state.update(await node(state))
        route = _route_after_context(state)
        if route == "clarify":
            state.update(await self.owner.clarify(state))
            return state
        if route == "action":
            state.update(await self.owner.handle_action(state))
            state.update(await self.owner.failure(state))
            if _route_after_failure(state) == "end":
                return state
        else:
            state.update(await self.owner.retrieve(state))
            state.update(await self.owner.evaluate_sufficiency(state))
            if _route_after_sufficiency(state) == "clarify":
                state.update(await self.owner.clarify(state))
                return state
        state.update(await self.owner.generate_answer(state))
        return state


def _route_after_context(state: AssistantState) -> Literal["clarify", "retrieve", "action"]:
    if state.get("unsafe") or state.get("out_of_domain") or state.get("ambiguous"):
        return "clarify"
    if state.get("intent") in {"reminder", "light"}:
        return "action"
    return "retrieve"


def _route_after_sufficiency(state: AssistantState) -> Literal["answer", "clarify"]:
    return "answer" if state.get("sufficient") else "clarify"


def _route_after_failure(state: AssistantState) -> Literal["answer", "end"]:
    return "end" if state.get("answer") else "answer"


def _select_plant(garden: list[dict], plant_hint: str | None, message: str) -> tuple[dict | None, bool]:
    haystack = f"{plant_hint or ''} {message}".casefold()
    matches = [
        plant
        for plant in garden
        if any(
            value and str(value).casefold() in haystack
            for value in (plant.get("nickname"), plant.get("scientific_name"), plant.get("common_name"))
        )
    ]
    if len(matches) == 1:
        return matches[0], False
    if len(matches) > 1:
        return None, True
    if plant_hint:
        return {"scientific_name": plant_hint, "id": None}, False
    references_plant = any(word in message.casefold() for word in ("mi planta", "esta planta", "esa planta"))
    return (garden[0], False) if len(garden) == 1 else (None, references_plant and len(garden) > 1)


def _topic_for_message(message: str) -> str:
    if any(word in message for word in ("agua", "riego", "regar", "watering")):
        return "watering"
    if any(word in message for word in ("luz", "sol", "sombra", "light")):
        return "light"
    if any(word in message for word in ("plaga", "hongo", "pest")):
        return "pests"
    return "care"


def _sources_from_retrieval(retrieval: object) -> list[dict]:
    chunks: list[KnowledgeChunk] = list(getattr(retrieval, "chunks", []) or [])
    sources = []
    seen = set()
    for chunk in chunks:
        if chunk.source_url in seen:
            continue
        seen.add(chunk.source_url)
        sources.append(
            {
                "title": chunk.metadata.get("title") if isinstance(chunk.metadata, dict) else None,
                "url": chunk.source_url,
                "domain": chunk.source_domain,
                "confidence": chunk.confidence,
            }
        )
    return sources


def _extract_due_at(message: str) -> datetime | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})[ T](\d{2}:\d{2})", message)
    if not match:
        return None
    value = f"{match.group(1)}T{match.group(2)}"
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _extract_recurrence(message: str) -> str | None:
    lowered = message.casefold()
    if "seman" in lowered:
        return "weekly"
    if "mens" in lowered:
        return "monthly"
    if "diari" in lowered:
        return "daily"
    return None


def _extract_reminder_action(message: str) -> str | None:
    lowered = message.casefold()
    for action in ("regar", "fertilizar", "podar", "revisar plagas", "medir luz"):
        if action in lowered:
            return action
    return None


def _wants_reminder_suggestion(message: str) -> bool:
    lowered = message.casefold()
    return any(
        term in lowered
        for term in (
            "sugeri",
            "sugerí",
            "sugerencia",
            "recomend",
            "propon",
            "conviene",
            "deberia",
            "debería",
        )
    )


def _display_plant(plant: dict) -> str:
    return str(plant.get("nickname") or plant.get("common_name") or plant.get("scientific_name"))


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."
