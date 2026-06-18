from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_current_provider_fallbacks: ContextVar[list[dict[str, Any]]] = ContextVar(
    "current_provider_fallbacks", default=[]
)


def get_provider_fallbacks() -> list[dict[str, Any]]:
    return list(_current_provider_fallbacks.get())


def record_provider_fallback(metadata: dict[str, Any]) -> None:
    fallbacks = list(_current_provider_fallbacks.get())
    fallbacks.append(metadata)
    _current_provider_fallbacks.set(fallbacks)


def clear_provider_fallbacks() -> None:
    _current_provider_fallbacks.set([])
