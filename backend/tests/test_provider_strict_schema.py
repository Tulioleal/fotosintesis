"""Tests for the shared OpenAI strict-mode JSON schema sanitizer."""

from __future__ import annotations

import pytest

from app.providers.schemas.strict_mode import (
    STRICT_SCALAR_TYPES,
    STRICT_UNSUPPORTED_KEYS,
    to_openai_strict_schema,
)


def test_to_openai_strict_schema_normalizes_simple_object() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
        },
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    assert result["type"] == "object"
    assert result["additionalProperties"] is False
    assert sorted(result["required"]) == ["count", "name"]
    assert result["properties"]["name"]["type"] == "string"
    assert result["properties"]["count"]["type"] == "integer"


def test_to_openai_strict_schema_preserves_nullable_union_types() -> None:
    schema = {
        "type": "object",
        "properties": {
            "nickname": {"type": ["string", "null"]},
        },
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    assert result["properties"]["nickname"]["type"] == ["string", "null"]


def test_to_openai_strict_schema_rejects_ref_construction() -> None:
    schema = {
        "type": "object",
        "properties": {
            "child": {"$ref": "#/definitions/Child"},
        },
        "definitions": {"Child": {"type": "string"}},
    }
    assert to_openai_strict_schema(schema) is None
    assert "$ref" in STRICT_UNSUPPORTED_KEYS


def test_to_openai_strict_schema_rejects_oneOf_construction() -> None:
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ],
            },
        },
    }
    assert to_openai_strict_schema(schema) is None
    assert "oneOf" in STRICT_UNSUPPORTED_KEYS


def test_to_openai_strict_schema_rejects_pattern_properties() -> None:
    schema = {
        "type": "object",
        "patternProperties": {
            "^x_": {"type": "string"},
        },
    }
    assert to_openai_strict_schema(schema) is None
    assert "patternProperties" in STRICT_UNSUPPORTED_KEYS


def test_to_openai_strict_schema_rejects_non_object_root() -> None:
    schema = {"type": "string"}
    assert to_openai_strict_schema(schema) is None


def test_to_openai_strict_schema_handles_nested_arrays() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                },
            },
        },
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    items = result["properties"]["items"]
    assert items["type"] == "array"
    assert items["items"]["type"] == "object"
    assert items["items"]["additionalProperties"] is False
    assert items["items"]["required"] == ["id"]


def test_to_openai_strict_schema_preserves_enums() -> None:
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["a", "b", "c"]},
        },
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    assert result["properties"]["status"]["enum"] == ["a", "b", "c"]


def test_to_openai_strict_schema_preserves_description_and_bounds() -> None:
    schema = {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "description": "confidence score",
                "minimum": 0,
                "maximum": 1,
            },
        },
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    score = result["properties"]["score"]
    assert score["description"] == "confidence score"
    assert score["minimum"] == 0
    assert score["maximum"] == 1


def test_to_openai_strict_schema_rejects_array_without_items() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array"},
        },
    }
    assert to_openai_strict_schema(schema) is None


@pytest.mark.parametrize("scalar", sorted(STRICT_SCALAR_TYPES))
def test_to_openai_strict_schema_accepts_all_scalar_types(scalar: str) -> None:
    schema = {
        "type": "object",
        "properties": {"value": {"type": scalar}},
    }
    result = to_openai_strict_schema(schema)
    assert result is not None
    assert result["properties"]["value"]["type"] == scalar
