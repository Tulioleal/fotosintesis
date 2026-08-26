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
        canonical_species_key: str | None = None,
        accepted_gbif_key: int | None = None,
        required_aspects: list[str] | None = None,
        question: str | None = None,
        filters: KnowledgeRetrievalFilters | None = None,
        min_existing_chunks: int = 1,
    ) -> KnowledgeAcquisitionResult:
        filters = filters or KnowledgeRetrievalFilters(
            scientific_name=scientific_name,
            topic=topic,
            review_status=ReviewStatus.auto_ingested,
        )
        query_text = _retrieval_query_text(
            scientific_name=scientific_name,
            topic=topic,
            required_aspects=required_aspects or [],
            question=question,
        )
        query_embedding = await self._query_embedding(query_text)
        try:
            ordinary = await self.vector_index.retrieve_chunks(
                filters,
                query_text=query_text,
                query_embedding=query_embedding,
            )
        except Exception:
            await self.repository.rollback()
            return _degraded_result(
                scientific_name,
                topic,
                [],
                "LlamaIndex pgvector retrieval failed; returning a limited result.",
            )

        enrichment: list = []
        if canonical_species_key and required_aspects:
            enrichment = await self._retrieve_enrichment_chunks(
                scientific_name=scientific_name,
                topic=topic,
                canonical_species_key=canonical_species_key,
                accepted_gbif_key=accepted_gbif_key,
                required_aspects=required_aspects,
                question=question,
            )

        existing = _deduplicate_chunks([*enrichment, *ordinary])[:5]

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
                    search_candidates=search_results,
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
                search_candidates=search_results,
            )
        except Exception:
            await self.repository.rollback()
            return _degraded_result(
                scientific_name,
                topic,
                existing,
                "Trusted acquisition failed; returning the best available partial evidence.",
            )

    async def _query_embedding(self, query_text: str) -> list[float]:
        result = await self.providers.embeddings.create_embeddings([query_text])
        return result.embeddings[0] if result.embeddings else []

    async def _retrieve_enrichment_chunks(
        self,
        *,
        scientific_name: str,
        topic: str,
        canonical_species_key: str,
        accepted_gbif_key: int | None,
        required_aspects: list[str],
        question: str | None,
    ) -> list:
        """Retrieve enrichment evidence with coverage-balanced per-aspect
        filtering so unrelated higher-scoring chunks can never displace
        requested-aspect coverage before the top-k limit."""
        distinct_aspects = list(dict.fromkeys(aspect for aspect in required_aspects if aspect))
        if not distinct_aspects:
            return []
        query_text = _retrieval_query_text(
            scientific_name=scientific_name,
            topic=topic,
            required_aspects=required_aspects,
            question=question,
        )
        query_embedding = await self._query_embedding(query_text)
        return await retrieve_balanced_enrichment(
            vector_index=self.vector_index,
            canonical_species_key=canonical_species_key,
            accepted_gbif_key=accepted_gbif_key,
            required_aspects=distinct_aspects,
            query_text=query_text,
            query_embedding=query_embedding,
            per_aspect_limit=5,
            budget=20,
        )

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
            "Create a structured botanical knowledge document as JSON using only these trusted sources. "
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


def _retrieval_query_text(
    *, scientific_name: str, topic: str, required_aspects: list[str], question: str | None
) -> str:
    parts = [scientific_name, topic]
    parts.extend(aspect.replace("_", " ") for aspect in required_aspects if aspect)
    if question and question.strip():
        parts.append(question.strip())
    return " ".join(part for part in parts if part).strip()


def balance_enrichment_chunks(
    hits_by_aspect: dict[str, list],
    *,
    budget: int,
) -> list:
    """Round-robin ordering across requested aspects.

    Each requested aspect contributes its first candidate before any aspect
    contributes a second, so one aspect's high-scoring unrelated hits cannot
    displace requested-aspect coverage before the bounded budget is reached.
    Candidates are deduplicated by stable chunk identity. The returned list
    is capped at ``budget``.
    """
    if budget <= 0:
        return []
    ordered: list = []
    ordered_ids: set[str] = set()
    if not hits_by_aspect:
        return ordered
    aspects = list(hits_by_aspect)
    longest = max(len(hits_by_aspect[aspect]) for aspect in aspects)
    for round_index in range(longest):
        for aspect in aspects:
            if len(ordered) >= budget:
                return ordered
            candidates = hits_by_aspect[aspect]
            if round_index >= len(candidates):
                continue
            chunk = candidates[round_index]
            key = str(getattr(chunk, "id", None) or hash(chunk.content))
            if key in ordered_ids:
                continue
            ordered_ids.add(key)
            ordered.append(chunk)
    return ordered[:budget]


async def retrieve_balanced_enrichment(
    *,
    vector_index,
    canonical_species_key: str,
    accepted_gbif_key: int | None,
    required_aspects: list[str],
    query_text: str,
    query_embedding: list[float],
    per_aspect_limit: int = 5,
    budget: int = 20,
) -> list:
    """Aspect-filtered enrichment retrieval with coverage-balanced ordering.

    Each requested aspect runs one pgvector query filtered to canonical
    species identity, confirmed-plant enrichment evidence, trusted
    provenance, auto-ingested review status, and that covered aspect. The
    per-aspect hits are balanced round-robin and deduplicated by stable chunk
    ID. Filtering selects candidates only; semantic judging remains
    authoritative for coverage.
    """
    distinct_aspects = list(
        dict.fromkeys(aspect for aspect in required_aspects if aspect)
    )
    if not distinct_aspects:
        return []
    hits_by_aspect: dict[str, list] = {}
    for aspect in distinct_aspects:
        try:
            candidates = await vector_index.retrieve_chunks(
                KnowledgeRetrievalFilters(
                    canonical_species_key=canonical_species_key,
                    accepted_gbif_key=accepted_gbif_key,
                    evidence_type="confirmed_plant_enrichment",
                    source_provenance="trusted",
                    review_status=ReviewStatus.auto_ingested,
                    covered_aspect=aspect,
                ),
                query_text=query_text,
                query_embedding=query_embedding,
                limit=per_aspect_limit,
            )
        except Exception:
            continue
        valid: list = []
        for chunk in candidates:
            validations = chunk.metadata.get("validation_provenance")
            if not isinstance(validations, list):
                continue
            covered = set(chunk.metadata.get("covered_aspects") or [])
            if aspect not in covered:
                continue
            if not any(
                isinstance(v, dict)
                and aspect in (v.get("covered_aspects") or [])
                for v in validations
            ):
                continue
            if chunk.id is None:
                continue
            valid.append(chunk)
        if valid:
            hits_by_aspect[aspect] = valid
    return balance_enrichment_chunks(hits_by_aspect, budget=budget)


def _degraded_result(
    scientific_name: str,
    topic: str,
    chunks: list,
    limitation: str,
    search_candidates: list[SearchResult] | None = None,
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
        search_candidates=search_candidates or [],
    )


def _content_from_sources(scientific_name: str, topic: str, sources: list[SearchResult]) -> str:
    evidence = " ".join(f"{source.title}: {source.snippet}" for source in sources)
    return f"Auto-ingested evidence for {scientific_name} about {topic}. {evidence}"


def _normalize_domain(domain: str) -> str:
    return domain.lower().removeprefix("www.").strip()


def _deduplicate_chunks(chunks: list) -> list:
    seen: set[str] = set()
    result: list = []
    for chunk in chunks:
        key = str(getattr(chunk, "id", None) or chunk.content[:80])
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result
