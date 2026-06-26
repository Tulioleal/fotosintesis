"""OpenAI vision and judge response schemas."""

from __future__ import annotations

from typing import Any


VISION_PROMPT = """
Analyze this plant image. Return JSON with description and candidates. Each candidate must include
scientific_name, common_name, confidence_label, confidence_score and visible_traits.
""".strip()


VISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "Concise textual description of the plant image.",
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scientific_name": {
                        "type": "string",
                        "description": "Scientific name of the candidate plant.",
                    },
                    "common_name": {
                        "type": ["string", "null"],
                        "description": "Common name of the candidate plant, or null when unknown.",
                    },
                    "confidence_label": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "inconclusive"],
                        "description": "Confidence bucket for this candidate.",
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "description": "Numeric confidence score, or null when unavailable.",
                    },
                    "visible_traits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Visible plant traits supporting the candidate.",
                    },
                },
                "required": [
                    "scientific_name",
                    "common_name",
                    "confidence_label",
                    "confidence_score",
                    "visible_traits",
                ],
                "additionalProperties": False,
            },
            "description": "Ranked list of candidate plant identifications.",
        },
    },
    "required": ["description", "candidates"],
    "additionalProperties": False,
}


JUDGE_DEFAULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["full", "partial", "insufficient", "contradictory"],
            "description": "Answerability status assigned by the judge.",
        },
        "covered_aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requested domain-qualified aspects directly supported by evidence.",
        },
        "missing_aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requested domain-qualified aspects not directly supported by evidence.",
        },
        "source_support": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "Specific claim that the evidence supports.",
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs that support the claim.",
                    },
                    "covered_aspects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Aspects supported by this claim.",
                    },
                    "evidence_quote": {
                        "type": ["string", "null"],
                        "description": "Verbatim evidence supporting the claim, or null.",
                    },
                    "confidence": {
                        "type": ["number", "null"],
                        "description": "Confidence score for this claim, or null.",
                    },
                },
                "required": [
                    "claim",
                    "source_urls",
                    "covered_aspects",
                    "evidence_quote",
                    "confidence",
                ],
                "additionalProperties": False,
            },
            "description": "Per-claim source support evidence.",
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_a": {
                        "type": "string",
                        "description": "First conflicting claim.",
                    },
                    "claim_b": {
                        "type": "string",
                        "description": "Second conflicting claim.",
                    },
                    "source_a_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs supporting claim_a.",
                    },
                    "source_b_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs supporting claim_b.",
                    },
                },
                "required": ["claim_a", "claim_b", "source_a_urls", "source_b_urls"],
                "additionalProperties": False,
            },
            "description": "Contradictory claims detected across sources.",
        },
        "confidence": {
            "type": "number",
            "description": "Numeric confidence score between 0 and 1.",
        },
        "score": {
            "type": "number",
            "description": "Numeric score kept aligned with confidence for compatibility.",
        },
        "passed": {
            "type": "boolean",
            "description": "True only when status is full.",
        },
        "reasons": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short explanations for the status decision.",
        },
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
    "additionalProperties": False,
}


def rubric_judge_schema(rubric: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rubric, dict):
        return JUDGE_DEFAULT_SCHEMA
    explicit = rubric.get("output_schema") or rubric.get("response_schema")
    if isinstance(explicit, dict):
        return explicit
    return JUDGE_DEFAULT_SCHEMA
