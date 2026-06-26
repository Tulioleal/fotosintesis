"""OpenAI provider package.

Adapter modules under :mod:`app.providers.openai` each own a single
OpenAI capability (model, vision, search, embeddings, judge).
"""

from app.providers.errors import OpenAIProviderError
from app.providers.openai.embeddings import OpenAIEmbeddingProvider
from app.providers.openai.judge import OpenAIJudgeProvider
from app.providers.openai.model import OpenAIModelProvider
from app.providers.openai.response_schemas import (
    JUDGE_DEFAULT_SCHEMA,
    VISION_PROMPT,
    VISION_SCHEMA,
    rubric_judge_schema,
)
from app.providers.schemas.strict_mode import to_openai_strict_schema
from app.providers.openai.search import OpenAISearchProvider
from app.providers.openai.vision import OpenAIVisionProvider

_to_openai_strict_schema = to_openai_strict_schema

__all__ = [
    "OpenAIEmbeddingProvider",
    "OpenAIJudgeProvider",
    "OpenAIModelProvider",
    "OpenAISearchProvider",
    "OpenAIVisionProvider",
    "OpenAIProviderError",
    "_to_openai_strict_schema",
    "JUDGE_DEFAULT_SCHEMA",
    "VISION_PROMPT",
    "VISION_SCHEMA",
    "rubric_judge_schema",
]
