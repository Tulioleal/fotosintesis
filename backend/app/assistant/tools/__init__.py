"""Assistant tools package.

Modules under :mod:`app.assistant.tools` group ingestion helpers,
trusted-source filters, dataclasses, constants, and facade methods by
capability.
"""

from app.assistant.tools.facade import AssistantTools
from app.assistant.tools.types import (
    AssistantFailureMetadata,
    ProviderFailureEntry,
    ToolResult,
    build_assistant_failure_metadata,
)

__all__ = [
    "AssistantFailureMetadata",
    "AssistantTools",
    "ProviderFailureEntry",
    "ToolResult",
    "build_assistant_failure_metadata",
]
