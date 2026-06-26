"""OpenAI strict-mode JSON schema sanitization.

The strict-mode formatter transforms a JSON Schema fragment into a
form that the OpenAI Responses API can validate. Constructs that the
strict-mode spec rejects (``$ref``, ``oneOf``, ``allOf``, ``patternProperties``,
unevaluated properties, etc.) cause the function to raise
:class:`StrictSchemaUnsupported`; the caller is expected to fall back
to JSON object mode in that case.
"""

from __future__ import annotations

from typing import Any

STRICT_UNSUPPORTED_KEYS: frozenset[str] = frozenset({
    "$ref",
    "$dynamicRef",
    "$anchor",
    "$id",
    "$schema",
    "oneOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "dependencies",
    "dependentSchemas",
    "dependentRequired",
    "patternProperties",
    "additionalItems",
    "unevaluatedProperties",
    "unevaluatedItems",
})

STRICT_SCALAR_TYPES: frozenset[str] = frozenset({"string", "number", "integer", "boolean"})


class StrictSchemaUnsupported(Exception):
    """Raised when a schema uses strict-mode-incompatible constructs."""


def to_openai_strict_schema(schema: Any) -> dict[str, Any] | None:
    """Convert a JSON Schema fragment into an OpenAI strict-mode form.

    Returns a sanitized copy with the following transformations:

    - All object schemas have ``additionalProperties: false`` and a complete
      ``required`` list (every property is marked as required, matching the
      strict-mode requirement that all properties be present in every
      response).
    - ``description`` and ``enum`` values are preserved.
    - Nullable scalar fields written as ``{"type": ["string", "null"]}``
      are preserved verbatim because OpenAI strict mode accepts that
      list-of-types form.
    - Nested object, array, and scalar subschemas are normalized recursively.

    Returns ``None`` when the schema contains any construct that strict
    mode does not accept or when the input is not a JSON-Schema-shaped
    object. The caller is expected to fall back to JSON object mode
    whenever ``None`` is returned.
    """
    try:
        normalized = _sanitize_strict_node(schema)
    except StrictSchemaUnsupported:
        return None
    if not isinstance(normalized, dict):
        return None
    if normalized.get("type") != "object":
        return None
    return normalized


def _sanitize_strict_node(node: Any) -> Any:
    if node is None:
        return None
    if not isinstance(node, dict):
        raise StrictSchemaUnsupported()
    for key in node:
        if key in STRICT_UNSUPPORTED_KEYS:
            raise StrictSchemaUnsupported()
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        return _sanitize_union_type(node, raw_type)
    if raw_type is None:
        if "enum" in node:
            return _sanitize_enum_node(node)
        if "properties" in node or "additionalProperties" in node:
            return _sanitize_object_node(node)
        if "items" in node:
            return _sanitize_array_node(node)
        return _sanitize_scalar_node(node)
    if raw_type in STRICT_SCALAR_TYPES:
        return _sanitize_scalar_node(node)
    if raw_type == "array":
        return _sanitize_array_node(node)
    if raw_type == "object":
        return _sanitize_object_node(node)
    if raw_type == "null":
        return {"type": "null"}
    raise StrictSchemaUnsupported()


def _sanitize_union_type(node: dict[str, Any], types: list[Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in node.items():
        if key == "type":
            continue
        sanitized[key] = _copy_passthrough(value)
    normalized_types: list[Any] = []
    for entry in types:
        if not isinstance(entry, str):
            raise StrictSchemaUnsupported()
        if entry == "null":
            normalized_types.append("null")
            continue
        if entry in STRICT_SCALAR_TYPES or entry in {"array", "object"}:
            normalized_types.append(entry)
            continue
        raise StrictSchemaUnsupported()
    if not normalized_types:
        raise StrictSchemaUnsupported()
    sanitized["type"] = normalized_types
    return sanitized


def _sanitize_scalar_node(node: dict[str, Any]) -> dict[str, Any]:
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        return _sanitize_union_type(node, raw_type)
    if raw_type not in STRICT_SCALAR_TYPES:
        raise StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"type": raw_type}
    if "enum" in node and isinstance(node["enum"], list):
        sanitized["enum"] = [_enum_value(value) for value in node["enum"]]
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    if "minimum" in node and isinstance(node["minimum"], (int, float)):
        sanitized["minimum"] = node["minimum"]
    if "maximum" in node and isinstance(node["maximum"], (int, float)):
        sanitized["maximum"] = node["maximum"]
    return sanitized


def _sanitize_enum_node(node: dict[str, Any]) -> dict[str, Any]:
    values = node.get("enum")
    if not isinstance(values, list) or not values:
        raise StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"enum": [_enum_value(value) for value in values]}
    raw_type = node.get("type")
    if isinstance(raw_type, str) and raw_type in STRICT_SCALAR_TYPES:
        sanitized["type"] = raw_type
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    return sanitized


def _sanitize_array_node(node: dict[str, Any]) -> dict[str, Any]:
    items = node.get("items")
    if items is None:
        raise StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"type": "array", "items": _sanitize_strict_node(items)}
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    if "minItems" in node and isinstance(node["minItems"], int):
        sanitized["minItems"] = node["minItems"]
    if "maxItems" in node and isinstance(node["maxItems"], int):
        sanitized["maxItems"] = node["maxItems"]
    return sanitized


def _sanitize_object_node(node: dict[str, Any]) -> dict[str, Any]:
    properties = node.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise StrictSchemaUnsupported()
    sanitized_properties: dict[str, Any] = {}
    for name, value in properties.items():
        if not isinstance(name, str) or not name:
            raise StrictSchemaUnsupported()
        sanitized_properties[name] = _sanitize_strict_node(value)
    required = list(sanitized_properties.keys())
    sanitized: dict[str, Any] = {
        "type": "object",
        "properties": sanitized_properties,
        "required": required,
        "additionalProperties": False,
    }
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    return sanitized


def _copy_passthrough(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy_passthrough(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_passthrough(item) for item in value]
    return value


def _enum_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
