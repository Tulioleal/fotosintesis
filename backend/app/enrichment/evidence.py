from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.exc import IntegrityError

from app.enrichment.identity import CanonicalSpeciesIdentity
from app.knowledge.rag import KnowledgeVectorIndex, OrchestratedKnowledgeIngestion
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    EnrichmentEvidenceMetadata,
    EnrichmentEvidenceState,
    KnowledgeDocumentInput,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.interfaces import EmbeddingProvider


EXPECTED_ENRICHMENT_CONSTRAINTS = {
    "knowledge_documents_pkey",
    "uq_knowledge_documents_enrichment_content_identity",
}


def _normalized_hash(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def enrichment_content_key(metadata: EnrichmentEvidenceMetadata) -> str:
    raw = json.dumps(
        {
            "species": metadata.canonical_species_key,
            "source": str(metadata.canonical_source_url).rstrip("/"),
            "source_version": metadata.source_version,
            "content_hash": metadata.normalized_content_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def stable_enrichment_document_id(content_key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"enrichment-content:{content_key}")


def stable_enrichment_chunk_id(content_key: str, chunk_index: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"enrichment-content:{content_key}:chunk:{chunk_index}")


def _is_expected_enrichment_conflict(exc: IntegrityError) -> bool:
    original = exc.orig
    constraint_name = getattr(original, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(
            getattr(original, "diag", None), "constraint_name", None
        )
    if constraint_name in EXPECTED_ENRICHMENT_CONSTRAINTS:
        return True
    return getattr(original, "sqlstate", None) == "23505"


@dataclass(frozen=True)
class AcceptedEnrichmentClaim:
    claim: str
    evidence_quote: str
    source_url: str
    source_title: str
    source_domain: str
    source_version: str
    source_retrieved_at: datetime
    source_published_at: datetime | None
    supported_aspects: tuple[str, ...]
    confidence: float

    @property
    def persisted_content(self) -> str:
        return f"{self.claim.strip()}\n\nSource evidence: {self.evidence_quote.strip()}"


class EnrichmentEvidencePersistenceService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        vector_index: KnowledgeVectorIndex,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.repository = repository
        self.vector_index = vector_index
        self.embedding_provider = embedding_provider

    async def persist_claim_relational(
        self,
        *,
        identity: CanonicalSpeciesIdentity,
        taxonomy_provenance_id: UUID,
        claim: AcceptedEnrichmentClaim,
    ) -> EnrichmentEvidenceState:
        if not claim.supported_aspects:
            raise ValueError("accepted enrichment evidence requires supported aspects")
        content = claim.persisted_content
        metadata = EnrichmentEvidenceMetadata(
            canonical_species_key=identity.key,
            accepted_gbif_key=identity.accepted_gbif_key,
            normalized_binomial=identity.normalized_binomial,
            canonical_source_url=claim.source_url,
            canonical_source_domain=claim.source_domain,
            source_version=claim.source_version,
            normalized_content_hash=_normalized_hash(content),
            source_retrieved_at=claim.source_retrieved_at,
            source_published_at=claim.source_published_at,
            enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        content_key = enrichment_content_key(metadata)
        existing = await self.repository.get_enrichment_evidence_state(metadata)
        if existing is not None:
            await self.repository.add_enrichment_aspect_supports(
                document_id=existing.document_id,
                aspects=list(claim.supported_aspects),
                confidence=claim.confidence,
                review_status=ReviewStatus.auto_ingested,
            )
            await self.repository.session.commit()
            return existing

        document = KnowledgeDocumentInput(
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            title=claim.source_title or f"{identity.normalized_binomial} evidence",
            content=content,
            confidence=claim.confidence,
            review_status=ReviewStatus.auto_ingested,
            sources=[
                KnowledgeSourceInput(
                    title=claim.source_title or claim.source_domain,
                    url=claim.source_url,
                    source_domain=claim.source_domain,
                    retrieved_at=claim.source_retrieved_at,
                    published_at=claim.source_published_at,
                    validation_status="trusted",
                )
            ],
            metadata={
                "canonical_species_key": identity.key,
                "accepted_gbif_key": identity.accepted_gbif_key,
                "normalized_binomial": identity.normalized_binomial,
                "taxonomy_provenance_id": str(taxonomy_provenance_id),
                "covered_aspects": list(claim.supported_aspects),
                "evidence_type": "confirmed_plant_enrichment",
                "source_provenance": "trusted",
            },
        )
        prepared = await self.vector_index.prepare_document(
            document,
            embedding_provider=self.embedding_provider,
        )
        stable_ingestion = OrchestratedKnowledgeIngestion(
            chunks=[
                chunk.model_copy(
                    update={"id": stable_enrichment_chunk_id(content_key, index)}
                )
                for index, chunk in enumerate(prepared.chunks)
            ],
            embeddings=prepared.embeddings,
            provider=prepared.provider,
            model=prepared.model,
        )
        document_id = stable_enrichment_document_id(content_key)

        try:
            await self.vector_index.persist_enrichment_relational(
                document,
                ingestion=stable_ingestion,
                enrichment=metadata,
                document_id=document_id,
            )
            await self.repository.add_enrichment_aspect_supports(
                document_id=document_id,
                aspects=list(claim.supported_aspects),
                confidence=claim.confidence,
                review_status=ReviewStatus.auto_ingested,
            )
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()

            if not _is_expected_enrichment_conflict(exc):
                raise

            winner = await self.repository.get_enrichment_evidence_state(metadata)
            if winner is None:
                raise

            await self.repository.add_enrichment_aspect_supports(
                document_id=winner.document_id,
                aspects=list(claim.supported_aspects),
                confidence=claim.confidence,
                review_status=ReviewStatus.auto_ingested,
            )
            await self.repository.session.commit()
            return winner

        return EnrichmentEvidenceState(
            document_id=document_id,
            chunks=stable_ingestion.chunks,
            embeddings=stable_ingestion.embeddings,
            embedding_provider=stable_ingestion.provider,
            embedding_model=stable_ingestion.model,
        )

    async def ensure_claim_indexed(
        self,
        state: EnrichmentEvidenceState,
    ) -> None:
        await self.vector_index.ensure_vector_nodes(
            chunks=state.chunks,
            embeddings=state.embeddings,
            provider=state.embedding_provider,
            model=state.embedding_model,
        )

    async def record_validation(
        self,
        *,
        job_id: UUID,
        taxonomy_provenance_id: UUID,
        policy_version: int,
        required_aspects: list[str],
        covered_aspects: list[str],
        missing_aspects: list[str],
        answerability_status: str,
        judge_confidence: float,
        validation_metadata: dict[str, object],
        document_ids: list[UUID] | None = None,
    ) -> UUID:
        fingerprint = json.dumps(
            {
                "job": str(job_id),
                "policy": policy_version,
                "covered": sorted(covered_aspects),
                "missing": sorted(missing_aspects),
                "status": answerability_status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        validation_id = uuid5(
            NAMESPACE_URL, f"enrichment-validation:{fingerprint}"
        )
        await self.repository.add_enrichment_validation_run(
            validation_id=validation_id,
            job_id=job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
            policy_version=policy_version,
            required_aspects=required_aspects,
            covered_aspects=covered_aspects,
            missing_aspects=missing_aspects,
            answerability_status=answerability_status,
            judge_confidence=judge_confidence,
            validation_metadata=validation_metadata,
            document_ids=document_ids if document_ids else None,
        )
        await self.repository.session.commit()
        return validation_id


__all__ = [
    "AcceptedEnrichmentClaim",
    "EnrichmentEvidencePersistenceService",
    "enrichment_content_key",
    "stable_enrichment_chunk_id",
    "stable_enrichment_document_id",
]
