"""AppEmbeddingTransform: Bridge from app EmbeddingProvider to LlamaIndex BaseEmbedding."""

from __future__ import annotations

from typing import Any, Sequence

from app.providers.interfaces import EmbeddingProvider
from app.providers.types import EmbeddingResult


class AppEmbeddingTransform:
    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self.result: EmbeddingResult | None = None

    async def _aget_query_embedding(self, query: str) -> list[float]:
        result = await self.embedding_provider.create_embeddings([query])
        self.result = result
        return result.embeddings[0]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        result = await self.embedding_provider.create_embeddings([text])
        self.result = result
        return result.embeddings[0]

    async def _get_query_embedding(self, query: str) -> list[float]:
        return await self._aget_query_embedding(query)

    async def _get_text_embedding(self, text: str) -> list[float]:
        return await self._aget_text_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Synchronous batch embedding is not supported in this transform")

    def as_llamaindex_transform(
        self, transform_component_cls: type, metadata_mode_cls: type
    ) -> Any:
        parent = self

        class _Transform(transform_component_cls):
            async def acall(self, nodes: Sequence[Any], **kwargs: Any) -> Sequence[Any]:
                embeddable_nodes = []
                texts = []
                metadata = []
                for node in nodes:
                    text = node.get_content(metadata_mode=metadata_mode_cls.NONE).strip()
                    if not text:
                        continue
                    embeddable_nodes.append(node)
                    texts.append(text)
                    metadata.append(dict(getattr(node, "metadata", {}) or {}))

                if not texts:
                    parent.result = None
                    return nodes

                result = await parent.embedding_provider.create_embeddings(texts, metadata=metadata)
                if len(result.embeddings) != len(embeddable_nodes):
                    raise ValueError("Embedding count must match LlamaIndex node count")

                for node, embedding in zip(embeddable_nodes, result.embeddings, strict=True):
                    node.embedding = embedding

                parent.result = result
                return nodes

            def __call__(self, nodes: Sequence[Any], **kwargs: Any) -> Sequence[Any]:
                raise RuntimeError("AppEmbeddingTransform requires async LlamaIndex ingestion")

        return _Transform()


def from_base_embedding(provider: EmbeddingProvider) -> Any:
    return AppEmbeddingTransform(provider)


class PrecomputedEmbeddingOnly:
    """LlamaIndex BaseEmbedding subclass that disables direct embedding generation.

    The application always supplies precomputed embeddings via the app
    :class:`EmbeddingProvider`. Direct LlamaIndex embedding generation
    is intentionally disabled so any attempt to embed via LlamaIndex
    fails fast.
    """

    error_message = (
        "LlamaIndex must receive precomputed embeddings from the app EmbeddingProvider; "
        "direct LlamaIndex embedding generation is disabled."
    )

    @staticmethod
    def from_base_embedding(base_embedding_cls: type, embed_dim: int) -> Any:
        class _PrecomputedEmbeddingOnly(base_embedding_cls):
            def __init__(self) -> None:
                super().__init__(
                    model_name=f"precomputed-app-embedding-{embed_dim}d", embed_batch_size=1
                )

            def _get_query_embedding(self, query: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            async def _aget_query_embedding(self, query: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            def _get_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            async def _aget_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

        return _PrecomputedEmbeddingOnly()
