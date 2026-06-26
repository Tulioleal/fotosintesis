"""Provider fallback wrapper package.

Adapter wrappers under :mod:`app.providers.wrappers` implement the
sequential provider fallback chain for each capability (model, judge,
search, vision). The shared chain runner is implemented in
:mod:`app.providers.wrappers.runner`.
"""

from app.providers.wrappers.exceptions import (
    AllProvidersFailedError,
)
from app.providers.wrappers.judge import JudgeEvaluationProviderFallbackWrapper
from app.providers.wrappers.model import ModelProviderFallbackWrapper
from app.providers.wrappers.runner import run_provider_chain
from app.providers.wrappers.search import SearchProviderFallbackWrapper
from app.providers.wrappers.vision import ImageAnalysisProviderFallbackWrapper

__all__ = [
    "AllProvidersFailedError",
    "ImageAnalysisProviderFallbackWrapper",
    "JudgeEvaluationProviderFallbackWrapper",
    "ModelProviderFallbackWrapper",
    "SearchProviderFallbackWrapper",
    "run_provider_chain",
]
