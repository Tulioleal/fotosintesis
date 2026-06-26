"""OpenAI embedding provider."""

from __future__ import annotations

from typing import Any

from app.providers.errors import OpenAIProviderError
from app.providers.interfaces import EmbeddingProvider
from app.providers.openai._client import (
    iter_any,
    logged_call,
    openai_client,
    value,
)
from app.providers.types import EmbeddingResult


def _embedding_index(item: Any) -> int:
    index = value(item, "index")
    if not isinstance(index, int):
        raise OpenAIProviderError("OpenAI embedding response item was missing an integer index")
    return index


def _embedding_vector(item: Any) -> list[float]:
    embedding = value(item, "embedding")
    if not isinstance(embedding, list) or not embedding:
        raise OpenAIProviderError("OpenAI embedding response item was missing an embedding vector")
    if not all(isinstance(value_item, int | float) for value_item in embedding):
        raise OpenAIProviderError("OpenAI embedding response vector contained non-numeric values")
    return [float(value_item) for value_item in embedding]


def _embeddings_from_response(response: Any, *, expected_count: int) -> list[list[float]]:
    data = iter_any(getattr(response, "data", None))
    if len(data) != expected_count:
        raise OpenAIProviderError(
            f"OpenAI embedding response returned {len(data)} items for {expected_count} inputs"
        )
    ordered = sorted(data, key=lambda item: _embedding_index(item))
    embeddings = [_embedding_vector(item) for item in ordered]
    if sorted(_embedding_index(item) for item in ordered) != list(range(expected_count)):
        raise OpenAIProviderError("OpenAI embedding response indexes did not match input order")
    return embeddings


def _supports_embedding_dimensions(model: str) -> bool:
    return model.startswith("text-embedding-3")


def _validate_embedding_dimensions(
    embeddings: list[list[float]], *, expected_dimension: int
) -> None:
    for index, embedding in enumerate(embeddings):
        if len(embedding) != expected_dimension:
            raise OpenAIProviderError(
                "OpenAI embedding response dimension mismatch: "
                f"expected {expected_dimension}, got {len(embedding)} at index {index}"
            )


def _embedding_metadata(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    total_tokens = value(usage, "total_tokens") if usage is not None else None
    prompt_tokens = value(usage, "prompt_tokens") if usage is not None else None
    return {
        key: value_obj
        for key, value_obj in {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
        }.items()
        if isinstance(value_obj, int)
    }


class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_name = "openai-embedding"

    def __init__(self, *, api_key: str, model: str, embedding_dimension: int | None = None) -> None:
        self.model = model
        self.embedding_dimension = embedding_dimension
        self._client = openai_client(api_key)

    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        model = kwargs.pop("model", self.model)
        kwargs.pop("metadata", None)
        if (
            self.embedding_dimension is not None
            and "dimensions" not in kwargs
            and _supports_embedding_dimensions(model)
        ):
            kwargs["dimensions"] = self.embedding_dimension
        response = await logged_call(
            provider=self.provider_name,
            role="embeddings",
            operation="create_embeddings",
            call=lambda: self._client.embeddings.create(model=model, input=texts, **kwargs),
        )
        embeddings = _embeddings_from_response(response, expected_count=len(texts))
        if self.embedding_dimension is not None:
            _validate_embedding_dimensions(embeddings, expected_dimension=self.embedding_dimension)
        return EmbeddingResult(
            provider=self.provider_name,
            model=model,
            embeddings=embeddings,
            metadata=_embedding_metadata(response),
        )
