from __future__ import annotations

from typing import Any

from app.assistant.graph.routes import (
    _route_after_context,
    _route_after_failure,
    _route_after_sufficiency,
    _route_after_web_fallback,
)
from app.assistant.graph.types import AssistantState


def _compile_graph(owner):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _SequentialGraph(owner)
    graph = StateGraph(AssistantState)
    for name in (
        "classify_intent",
        "load_user_context",
        "retrieve",
        "evaluate_sufficiency",
        "fallback_web_search",
        "handle_action",
        "generate_answer",
        "clarify",
        "failure",
    ):
        graph.add_node(name, getattr(owner, name))
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "load_user_context")
    graph.add_conditional_edges(
        "load_user_context",
        _route_after_context,
        {"clarify": "clarify", "retrieve": "retrieve", "action": "handle_action"},
    )
    graph.add_edge("retrieve", "evaluate_sufficiency")
    graph.add_conditional_edges(
        "evaluate_sufficiency",
        _route_after_sufficiency,
        {"answer": "generate_answer", "fallback": "fallback_web_search"},
    )
    graph.add_conditional_edges(
        "fallback_web_search",
        _route_after_web_fallback,
        {"answer": "generate_answer", "clarify": "clarify"},
    )
    graph.add_edge("handle_action", "failure")
    graph.add_conditional_edges(
        "failure",
        _route_after_failure,
        {"answer": "generate_answer", "end": END},
    )
    graph.add_edge("generate_answer", END)
    graph.add_edge("clarify", END)
    return graph.compile()


class _SequentialGraph:
    def __init__(self, owner) -> None:
        self.owner = owner
        self._node_callables: dict[str, Any] = {
            "classify_intent": owner.classify_intent,
            "load_user_context": owner.load_user_context,
            "retrieve": owner.retrieve,
            "evaluate_sufficiency": owner.evaluate_sufficiency,
            "fallback_web_search": owner.fallback_web_search,
            "handle_action": owner.handle_action,
            "generate_answer": owner.generate_answer,
            "clarify": owner.clarify,
            "failure": owner.failure,
        }

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
            if _route_after_sufficiency(state) == "fallback":
                state.update(await self.owner.fallback_web_search(state))
                if _route_after_web_fallback(state) == "clarify":
                    state.update(await self.owner.clarify(state))
                    return state
        state.update(await self.owner.generate_answer(state))
        return state


__all__ = ["_SequentialGraph", "_compile_graph"]
