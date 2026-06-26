"""Compatibility shim for the aspect metadata registry.

The real registry and helpers now live under ``app.assistant.aspects``.
This module remains as a small re-export surface so existing imports do
not need to change.
"""

from app.assistant.aspects import (
    REQUIRED_ASPECT_METADATA,
    RequiredAspectMetadata,
    aspect_query_terms,
    aspect_validation_guidance,
    is_safety_sensitive_aspect,
    metadata_for_aspect,
)

__all__ = [
    "REQUIRED_ASPECT_METADATA",
    "RequiredAspectMetadata",
    "aspect_query_terms",
    "aspect_validation_guidance",
    "is_safety_sensitive_aspect",
    "metadata_for_aspect",
]
