"""Gemini provider package.

Adapter modules under :mod:`app.providers.gemini` each own a single
Gemini capability (model, vision, search, judge).
"""

from app.providers.errors import GeminiProviderError
from app.providers.gemini.judge import GeminiJudgeProvider
from app.providers.gemini.model import GeminiModelProvider
from app.providers.gemini.response_schemas import (
    JUDGE_SCHEMA as _JUDGE_SCHEMA,
    VISION_PROMPT,
    VISION_SCHEMA as _VISION_SCHEMA,
)
from app.providers.gemini.search import (
    GeminiSearchProvider,
    _is_internal_redirect_url,
    _search_results_from_response,
)
from app.providers.gemini.vision import GeminiVisionProvider

__all__ = [
    "GeminiJudgeProvider",
    "GeminiModelProvider",
    "GeminiSearchProvider",
    "GeminiVisionProvider",
    "GeminiProviderError",
    "VISION_PROMPT",
    "_JUDGE_SCHEMA",
    "_VISION_SCHEMA",
    "_is_internal_redirect_url",
    "_search_results_from_response",
]
