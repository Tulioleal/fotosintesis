"""Server-authored progress events for assistant chat execution.

Events use a closed vocabulary mapped to graph stages, carry server-authored
Spanish labels, and are structurally whitelisted: prompts, provider payloads,
raw evidence bodies and injection internals can never serialize into a frame.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

# Closed stage vocabulary mapped 1:1 to graph node names plus terminal
# clarify/action/failure states.
STAGE_LABELS_ES: dict[str, str] = {
    "classify_intent": "Clasificando tu consulta",
    "load_user_context": "Revisando el contexto de tu planta",
    "retrieve": "Buscando evidencia en fuentes confiables",
    "evaluate_sufficiency": "Contrastando la informacion",
    "fallback_web_search": "Consultando fuentes externas confiables",
    "handle_action": "Preparando la accion solicitada",
    "generate_answer": "Redactando respuesta",
    "clarify": "Preparando una aclaracion",
    "failure": "Resolviendo un problema temporal",
}

StageListener = Callable[[dict[str, Any]], Awaitable[None]]


def build_stage_event(stage_id: str, index: int) -> dict[str, Any]:
    """Whitelisted stage event builder — the redaction boundary."""
    if stage_id not in STAGE_LABELS_ES:
        raise ValueError(f"Unknown assistant stage: {stage_id}")
    return {
        "type": "stage",
        "stage_id": stage_id,
        "label_es": STAGE_LABELS_ES[stage_id],
        "index": index,
    }


def build_result_event(payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "result", **payload}


def build_error_event(payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "error", **payload}


def sse_frame(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


HEARTBEAT_FRAME = ": ping\n\n"


class StageSequence:
    """Tracks monotonic non-repeating stage emission for one chat turn."""

    def __init__(self, listener: StageListener | None) -> None:
        self._listener = listener
        self._emitted: list[str] = []
        self._index = 0

    async def emit(self, stage_id: str) -> None:
        if self._listener is None or stage_id in self._emitted:
            return
        if stage_id not in STAGE_LABELS_ES:
            return
        self._emitted.append(stage_id)
        event = build_stage_event(stage_id, self._index)
        self._index += 1
        await self._listener(event)

    @property
    def active(self) -> bool:
        return self._listener is not None


__all__ = [
    "STAGE_LABELS_ES",
    "StageListener",
    "StageSequence",
    "build_error_event",
    "build_result_event",
    "build_stage_event",
    "sse_frame",
    "HEARTBEAT_FRAME",
]
