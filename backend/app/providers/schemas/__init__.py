"""Shared provider-owned JSON schemas and strict-mode schema helpers.

This package owns JSON-schema shapes and strict-mode formatting logic
that must be reused by every provider adapter. Putting these under
``app/providers/`` keeps provider adapters independent of feature-slice
internals.
"""

from app.providers.schemas.strict_mode import (
    STRICT_SCALAR_TYPES,
    STRICT_UNSUPPORTED_KEYS,
    StrictSchemaUnsupported,
    to_openai_strict_schema,
)

__all__ = [
    "STRICT_SCALAR_TYPES",
    "STRICT_UNSUPPORTED_KEYS",
    "StrictSchemaUnsupported",
    "to_openai_strict_schema",
]
