"""Tests for the compiled assistant graph topology.

These tests capture the expected node and edge set of the LangGraph topology
so the graph split into a package cannot accidentally change the
runtime structure.

The tests use a fake ``langgraph.graph`` module injected via ``sys.modules``
so they exercise ``_compile_graph``'s wiring without depending on the real
``langgraph`` package being installed.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.assistant.graph import AssistantGraph, _SequentialGraph, _compile_graph


EXPECTED_NODES: set[str] = {
    "classify_intent",
    "load_user_context",
    "retrieve",
    "evaluate_sufficiency",
    "fallback_web_search",
    "handle_action",
    "generate_answer",
    "clarify",
    "failure",
}


EXPECTED_EDGES: set[tuple[str, str]] = {
    (".__start__", "classify_intent"),
    ("classify_intent", "load_user_context"),
    ("load_user_context", "clarify"),
    ("load_user_context", "retrieve"),
    ("load_user_context", "handle_action"),
    ("retrieve", "evaluate_sufficiency"),
    ("evaluate_sufficiency", "generate_answer"),
    ("evaluate_sufficiency", "fallback_web_search"),
    ("fallback_web_search", "generate_answer"),
    ("fallback_web_search", "clarify"),
    ("handle_action", "failure"),
    ("failure", "generate_answer"),
    ("failure", ".__end__"),
    ("generate_answer", ".__end__"),
    ("clarify", ".__end__"),
}


class _FakeStateGraph:
    """Minimal stand-in for ``langgraph.graph.StateGraph`` that captures calls."""

    def __init__(self, state_type: Any = None) -> None:
        self.state_type = state_type
        self.nodes: dict[str, Any] = {}
        self.edges: set[tuple[str, str]] = set()

    def add_node(self, name: str, fn: Any) -> None:
        self.nodes[name] = fn

    def add_edge(self, source: Any, target: str) -> None:
        self.edges.add((str(source), target))

    def add_conditional_edges(
        self, source: str, path: Any, path_map: dict[str, str]
    ) -> None:
        for target in path_map.values():
            self.edges.add((source, target))

    def compile(self) -> _FakeStateGraph:
        return self


def _install_fake_langgraph(
    monkeypatch: pytest.MonkeyPatch, capture: dict[str, _FakeStateGraph]
) -> None:
    """Install a fake ``langgraph.graph`` module that records the StateGraph."""

    fake_pkg = types.ModuleType("langgraph")
    fake_graph = types.ModuleType("langgraph.graph")

    def factory(state_type: Any = None) -> _FakeStateGraph:
        instance = _FakeStateGraph(state_type)
        capture["graph"] = instance
        return instance

    fake_graph.StateGraph = factory
    fake_graph.START = ".__start__"
    fake_graph.END = ".__end__"
    fake_pkg.graph = fake_graph

    monkeypatch.setitem(sys.modules, "langgraph", fake_pkg)
    monkeypatch.setitem(sys.modules, "langgraph.graph", fake_graph)


class _TopologyOwner:
    """Bare-bones owner exposing the node callables used by the compiler."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def classify_intent(self, state):
        self.calls.append("classify_intent")
        return state

    def load_user_context(self, state):
        self.calls.append("load_user_context")
        return state

    def retrieve(self, state):
        self.calls.append("retrieve")
        return state

    def evaluate_sufficiency(self, state):
        self.calls.append("evaluate_sufficiency")
        return state

    def fallback_web_search(self, state):
        self.calls.append("fallback_web_search")
        return state

    def handle_action(self, state):
        self.calls.append("handle_action")
        return state

    def generate_answer(self, state):
        self.calls.append("generate_answer")
        return state

    def clarify(self, state):
        self.calls.append("clarify")
        return state

    def failure(self, state):
        self.calls.append("failure")
        return state


@pytest.fixture
def topology_owner() -> _TopologyOwner:
    return _TopologyOwner()


def test_compile_graph_uses_sequential_fallback_when_langgraph_missing(
    monkeypatch: pytest.MonkeyPatch, topology_owner: _TopologyOwner
) -> None:
    """When langgraph cannot be imported, the compiler falls back to a sequential graph."""

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def fake_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "langgraph.graph":
            raise ImportError("simulated langgraph absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    graph = _compile_graph(topology_owner)
    assert isinstance(graph, _SequentialGraph)


def test_compile_graph_topology_nodes_and_edges(
    monkeypatch: pytest.MonkeyPatch, topology_owner: _TopologyOwner
) -> None:
    """The compiled graph wires the expected node and edge set."""

    capture: dict[str, _FakeStateGraph] = {}
    _install_fake_langgraph(monkeypatch, capture)
    graph = _compile_graph(topology_owner)

    assert isinstance(graph, _FakeStateGraph)
    assert set(graph.nodes.keys()) == EXPECTED_NODES
    assert graph.edges == EXPECTED_EDGES
    assert capture["graph"] is graph


def test_compile_graph_includes_sequential_fallback_nodes(
    topology_owner: _TopologyOwner,
) -> None:
    """The sequential fallback exposes the same node set as the real topology."""

    graph = _SequentialGraph(topology_owner)
    assert set(graph._node_callables) == EXPECTED_NODES


def test_assistant_graph_constructor_uses_sequential_fallback_when_langgraph_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The :class:`AssistantGraph` instance composes the same node set."""

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def fake_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "langgraph.graph":
            raise ImportError("simulated langgraph absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    graph = AssistantGraph(tools=None)  # type: ignore[arg-type]
    assert isinstance(graph.graph, _SequentialGraph)
    assert set(graph.graph._node_callables) == EXPECTED_NODES
