"""Helpers for building persisted knowledge documents from tool inputs."""

from __future__ import annotations

from datetime import datetime, timezone

from app.assistant.tools.types import (
    EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE,
    TRUSTED_WEB_EVIDENCE_CONFIDENCE,
)
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.schemas import (
    KnowledgeDocumentInput,
    KnowledgeSourceInput,
    ReviewStatus,
)


def web_evidence_content(
    scientific_name: str, topic: str, evidence_items: list[TrustedPageEvidence]
) -> str:
    evidence = " ".join(
        f"{item.result.title}: {item.evidence_text} Source: {item.result.url}."
        for item in evidence_items
    )
    return f"Live web fallback evidence for {scientific_name} about {topic}. {evidence}"


def validated_claim_content(claim: dict[str, object]) -> str:
    aspects = ", ".join(str(aspect) for aspect in claim.get("covered_aspects") or [])
    return (
        f"Validated evidence for {claim.get('scientific_name')}. "
        f"Topic: {claim.get('topic')}. Covered aspects: {aspects}. "
        f"Claim: {claim.get('claim')}. Evidence quote: {claim.get('evidence_quote')}. "
        f"Source: {claim.get('source_url')}. Validation confidence: {claim.get('confidence')}."
    )


def web_evidence_confidence(evidence_items: list[TrustedPageEvidence]) -> float:
    if all(
        evidence.validation_status == "external_fallback"
        for evidence in evidence_items
    ):
        return EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE
    return TRUSTED_WEB_EVIDENCE_CONFIDENCE


def metadata_for_source(
    metadata: dict[str, object], item: TrustedPageEvidence
) -> dict[str, object]:
    source_metadata = dict(metadata)
    validations = metadata.get("source_validations")
    if isinstance(validations, list):
        for validation in validations:
            if not isinstance(validation, dict) or validation.get("url") != item.result.url:
                continue
            source_metadata["covered_aspects"] = list(validation.get("covered_aspects", []))
            source_metadata["validation_confidence"] = validation.get("validation_confidence", 0.0)
            break
    source_metadata.pop("source_validations", None)
    source_metadata["source_domain"] = item.result.source_domain
    return source_metadata


def build_web_evidence_document(
    *,
    scientific_name: str,
    topic: str,
    item: TrustedPageEvidence,
    metadata: dict[str, object],
    now: datetime | None = None,
) -> KnowledgeDocumentInput:
    moment = now or datetime.now(timezone.utc)
    confidence = web_evidence_confidence([item])
    return KnowledgeDocumentInput(
        scientific_name=scientific_name,
        topic=topic,
        title=f"{scientific_name}: {topic} web fallback evidence",
        content=web_evidence_content(scientific_name, topic, [item]),
        confidence=confidence,
        review_status=ReviewStatus.auto_ingested,
        metadata=metadata_for_source(metadata, item),
        sources=[
            KnowledgeSourceInput(
                title=item.result.title,
                url=item.result.url,
                source_domain=item.result.source_domain,
                retrieved_at=moment,
                validation_status=item.validation_status,
            )
        ],
    )


def build_validated_claim_document(
    *,
    claim: dict[str, object],
    now: datetime | None = None,
) -> KnowledgeDocumentInput | None:
    moment = now or datetime.now(timezone.utc)
    source_url = str(claim.get("source_url") or "")
    if not source_url:
        return None
    confidence = float(claim.get("confidence") or TRUSTED_WEB_EVIDENCE_CONFIDENCE)
    metadata = {
        "topic": claim.get("topic"),
        "required_aspects": list(claim.get("required_aspects") or []),
        "covered_aspects": list(claim.get("covered_aspects") or []),
        "missing_aspects": list(claim.get("missing_aspects") or []),
        "language": claim.get("language") or "es",
        "evidence_type": "validated_web_claim",
        "answerability_status": claim.get("answerability_status"),
        "validation_confidence": confidence,
        "source_support_claim": claim.get("claim"),
        "source_support_quote": claim.get("evidence_quote"),
        "persisted_from": "assistant_final_judge",
        "source_domain": claim.get("source_domain"),
    }
    return KnowledgeDocumentInput(
        scientific_name=str(claim.get("scientific_name") or ""),
        topic=str(claim.get("topic") or "care"),
        title=f"{claim.get('scientific_name')}: validated web claim",
        content=validated_claim_content(claim),
        confidence=confidence,
        review_status=ReviewStatus.auto_ingested,
        metadata=metadata,
        sources=[
            KnowledgeSourceInput(
                title=str(claim.get("source_title") or claim.get("source_domain") or source_url),
                url=source_url,
                source_domain=str(claim.get("source_domain") or ""),
                retrieved_at=moment,
                validation_status=str(claim.get("answerability_status") or "validated"),
            )
        ],
    )
