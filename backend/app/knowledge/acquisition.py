from datetime import datetime, timezone
from urllib.parse import quote, urlparse

from app.core.settings import get_settings
from app.knowledge.rag import KnowledgeVectorIndex
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    AcquisitionStatus,
    KnowledgeAcquisitionResult,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.factory import ProviderRegistry, get_provider_registry
from app.providers.types import SearchResult


class TrustedSourceValidator:
    def __init__(self, approved_domains: list[str] | None = None) -> None:
        self.approved_domains = {
            _normalize_domain(domain)
            for domain in (approved_domains or get_settings().trusted_source_domains)
        }

    def is_trusted(self, result: SearchResult) -> bool:
        parsed = urlparse(result.url)
        if parsed.scheme != "https":
            return False
        domain = _normalize_domain(result.source_domain or parsed.netloc)
        if not domain or domain != _normalize_domain(parsed.netloc):
            return False
        return any(
            domain == approved or domain.endswith(f".{approved}")
            for approved in self.approved_domains
        )

    def filter(self, results: list[SearchResult]) -> list[SearchResult]:
        return [result for result in results if self.is_trusted(result)]


class KnowledgeAcquisitionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        providers: ProviderRegistry | None = None,
        trusted_sources: TrustedSourceValidator | None = None,
        vector_index: KnowledgeVectorIndex | None = None,
    ) -> None:
        self.repository = repository
        self.providers = providers or get_provider_registry()
        self.trusted_sources = trusted_sources or TrustedSourceValidator()
        self.vector_index = vector_index or KnowledgeVectorIndex(repository)

    async def retrieve_or_acquire(
        self,
        *,
        scientific_name: str,
        topic: str,
        filters: KnowledgeRetrievalFilters | None = None,
        min_existing_chunks: int = 1,
    ) -> KnowledgeAcquisitionResult:
        filters = filters or KnowledgeRetrievalFilters(
            scientific_name=scientific_name,
            topic=topic,
            review_status=ReviewStatus.auto_ingested,
        )
        query_text = f"{scientific_name} {topic}"
        query_embedding = await self._query_embedding(scientific_name, topic)
        try:
            existing = await self.vector_index.retrieve_chunks(
                filters,
                query_text=query_text,
                query_embedding=query_embedding,
            )
        except Exception:
            return _degraded_result(
                scientific_name,
                topic,
                [],
                "LlamaIndex pgvector retrieval failed; returning a limited result.",
            )
        if len(existing) >= min_existing_chunks:
            return KnowledgeAcquisitionResult(status=AcquisitionStatus.retrieved, chunks=existing)

        try:
            search_results = await self.providers.search.search(
                f"{scientific_name} {topic} botanical care taxonomy",
                allowed_domains=sorted(self.trusted_sources.approved_domains),
            )
            trusted = self.trusted_sources.filter(search_results)
            if not trusted:
                return _degraded_result(
                    scientific_name,
                    topic,
                    existing,
                    "No trusted approved source was found for persistent knowledge ingestion.",
                )

            document = await self._generate_document(scientific_name, topic, trusted[:3])
            persisted = await self.vector_index.ingest_document(
                document,
                embedding_provider=self.providers.embeddings,
            )
            retrieved = await self.vector_index.retrieve_chunks(
                filters,
                query_text=query_text,
                query_embedding=query_embedding,
            )
            return KnowledgeAcquisitionResult(
                status=AcquisitionStatus.acquired,
                chunks=retrieved,
                document_id=persisted.id,
            )
        except Exception:
            return _degraded_result(
                scientific_name,
                topic,
                existing,
                "Trusted acquisition failed; returning the best available partial evidence.",
            )

    async def _query_embedding(self, scientific_name: str, topic: str) -> list[float]:
        result = await self.providers.embeddings.create_embeddings([f"{scientific_name} {topic}"])
        return result.embeddings[0] if result.embeddings else []

    async def _generate_document(
        self, scientific_name: str, topic: str, sources: list[SearchResult]
    ) -> KnowledgeDocumentInput:
        schema = {
            "type": "object",
            "required": ["title", "content", "confidence"],
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }
        prompt = (
            "Create a structured botanical knowledge document using only these trusted sources. "
            f"Species: {scientific_name}. Topic: {topic}. Sources: "
            + " | ".join(f"{source.title}: {source.snippet}" for source in sources)
        )
        generated = await self.providers.model.generate_json(prompt, schema=schema)
        data = generated.data
        now = datetime.now(timezone.utc)
        content = str(data.get("content") or _content_from_sources(scientific_name, topic, sources))
        return KnowledgeDocumentInput(
            scientific_name=scientific_name,
            topic=topic,
            title=str(data.get("title") or f"{scientific_name}: {topic}"),
            content=content,
            confidence=float(data.get("confidence") or 0.65),
            review_status=ReviewStatus.auto_ingested,
            sources=[
                KnowledgeSourceInput(
                    title=source.title,
                    url=source.url,
                    source_domain=_normalize_domain(source.source_domain),
                    retrieved_at=now,
                )
                for source in sources
            ],
        )


def _degraded_result(
    scientific_name: str,
    topic: str,
    chunks: list,
    limitation: str,
) -> KnowledgeAcquisitionResult:
    return KnowledgeAcquisitionResult(
        status=AcquisitionStatus.degraded,
        chunks=chunks,
        limitations=[limitation],
        retry_available=True,
        manual_search_url=(
            "https://www.google.com/search?q="
            f"{quote(f'{scientific_name} {topic} trusted botanical source')}"
        ),
    )


def _content_from_sources(scientific_name: str, topic: str, sources: list[SearchResult]) -> str:
    evidence = " ".join(f"{source.title}: {source.snippet}" for source in sources)
    return f"Auto-ingested evidence for {scientific_name} about {topic}. {evidence}"


def _normalize_domain(domain: str) -> str:
    return domain.lower().removeprefix("www.").strip()
