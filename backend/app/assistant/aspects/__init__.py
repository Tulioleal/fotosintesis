"""Aspect metadata package.

The structured :class:`RequiredAspectMetadata` registry, query terms,
validation guidance, and safety-sensitivity checks have moved into
this package. The top-level :mod:`app.assistant.aspect_metadata`
module remains as a re-export shim so existing imports continue to
work during the migration.
"""

from app.assistant.aspects.accessors import (
    aspect_query_terms,
    aspect_validation_guidance,
    is_safety_sensitive_aspect,
    metadata_for_aspect,
)
from app.assistant.aspects.registry import (
    REQUIRED_ASPECT_METADATA,
    RequiredAspectMetadata,
)

__all__ = [
    "REQUIRED_ASPECT_METADATA",
    "RequiredAspectMetadata",
    "aspect_query_terms",
    "aspect_validation_guidance",
    "is_safety_sensitive_aspect",
    "metadata_for_aspect",
]
