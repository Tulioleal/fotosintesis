"""OpenAI strict-mode JSON schema format builders."""

from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger
from app.providers.schemas.strict_mode import to_openai_strict_schema

logger = get_logger(__name__)


def log_provider_json_schema_fallback(
    *,
    provider: str,
    role: str,
    operation: str,
    schema_name: str | None,
    reason: str,
) -> None:
    logger.info(
        "provider json schema fallback",
        extra={
            "ctx_event": "provider_json_schema_fallback",
            "ctx_provider": provider,
            "ctx_role": role,
            "ctx_operation": operation,
            "ctx_schema_name": schema_name,
            "ctx_reason": reason,
        },
    )


def build_strict_text_format(
    *,
    schema: Any,
    name: str,
    provider: str,
    role: str,
    operation: str,
) -> dict[str, Any] | None:
    sanitized = to_openai_strict_schema(schema)
    if sanitized is None:
        log_provider_json_schema_fallback(
            provider=provider,
            role=role,
            operation=operation,
            schema_name=name,
            reason="schema cannot be safely sanitized for strict mode",
        )
        return None
    return {
        "type": "json_schema",
        "name": name,
        "schema": sanitized,
        "strict": True,
    }
