"""Gemini vision and judge response schemas."""

from __future__ import annotations

from typing import Any

from app.providers.schemas.shared_shapes import covered_aspects_array_schema


VISION_PROMPT = """
Analyze this plant image. Return JSON with description and candidates. Each candidate must include
scientific_name, common_name, confidence_label, confidence_score and visible_traits.
""".strip()


VISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scientific_name": {"type": "string"},
                    "common_name": {"type": "string", "nullable": True},
                    "confidence_label": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "inconclusive"],
                    },
                    "confidence_score": {"type": "number", "nullable": True},
                    "visible_traits": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["scientific_name", "visible_traits"],
            },
        },
    },
    "required": ["description", "candidates"],
}


JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["full", "partial", "insufficient", "contradictory"]},
        "covered_aspects": covered_aspects_array_schema(),
        "missing_aspects": covered_aspects_array_schema(),
        "source_support": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                    "covered_aspects": covered_aspects_array_schema(),
                    "evidence_quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["claim", "source_urls", "covered_aspects", "evidence_quote", "confidence"],
            },
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_a": {"type": "string"},
                    "claim_b": {"type": "string"},
                    "source_a_urls": {"type": "array", "items": {"type": "string"}},
                    "source_b_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim_a", "claim_b", "source_a_urls", "source_b_urls"],
            },
        },
        "confidence": {"type": "number"},
        "score": {"type": "number"},
        "passed": {"type": "boolean"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "status",
        "covered_aspects",
        "missing_aspects",
        "source_support",
        "contradictions",
        "confidence",
        "score",
        "passed",
        "reasons",
    ],
}
