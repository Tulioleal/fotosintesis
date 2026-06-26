"""Trusted-source filtering helpers for AssistantTools."""

from __future__ import annotations

from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence
from app.providers.types import SearchResult


def trusted_first_results(
    results: list[SearchResult], trusted_sources: TrustedSourceValidator
) -> list[SearchResult]:
    trusted = trusted_sources.filter(results)
    if trusted:
        return trusted
    return results[:1]


def is_external_fallback_selection(
    results: list[SearchResult], trusted_sources: TrustedSourceValidator
) -> bool:
    return bool(results) and not trusted_sources.is_trusted(results[0])


def persistable_page_evidence(
    results: list[SearchResult | TrustedPageEvidence],
    trusted_sources: TrustedSourceValidator,
    external_fallback_validation_status: str,
) -> list[TrustedPageEvidence]:
    trusted_items: list[TrustedPageEvidence] = []
    external_fallback_items: list[TrustedPageEvidence] = []
    for item in results:
        evidence = item if isinstance(item, TrustedPageEvidence) else TrustedPageEvidence(result=item)
        if trusted_sources.is_trusted(evidence.result):
            trusted_items.append(evidence)
        elif evidence.validation_status == external_fallback_validation_status:
            external_fallback_items.append(evidence)
    return trusted_items or external_fallback_items[:1]
