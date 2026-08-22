from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.assistant.aspect_metadata import aspect_query_terms
from app.assistant.care_contracts import RequiredAspect
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import EnrichmentPolicy
from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence, TrustedPageEvidenceFetcher
from app.observability.logging import get_logger
from app.providers.errors import ProviderError
from app.providers.interfaces import SearchProvider
from app.providers.wrappers import AllProvidersFailedError


logger = get_logger(__name__)


@dataclass(frozen=True)
class OfflineAcquisitionResult:
    searched_groups: tuple[tuple[RequiredAspect, ...], ...]
    evidence: tuple[TrustedPageEvidence, ...]

    @property
    def status(self) -> str:
        return "acquired" if self.evidence else "insufficient"


class OfflineEnrichmentAcquisitionService:
    """Bounded trusted acquisition for a semantically selected missing subset."""

    def __init__(
        self,
        *,
        search: SearchProvider,
        trusted_sources: TrustedSourceValidator,
        page_fetcher: TrustedPageEvidenceFetcher | None = None,
    ) -> None:
        self.search = search
        self.trusted_sources = trusted_sources
        self.page_fetcher = page_fetcher or TrustedPageEvidenceFetcher(trusted_sources)

    async def acquire(
        self,
        *,
        identity: CanonicalSpeciesIdentity,
        required_aspects: Sequence[RequiredAspect],
        acquisition_aspects: Sequence[RequiredAspect],
        policy: EnrichmentPolicy,
    ) -> OfflineAcquisitionResult:
        required = frozenset(required_aspects)
        missing = frozenset(acquisition_aspects)
        if not required or not missing <= required:
            raise ValueError("acquisition_aspects must be a non-empty subset of required_aspects")
        if required != policy.required_aspects:
            raise ValueError("required_aspects must match the selected enrichment policy")
        if identity.normalized_binomial is None:
            raise ValueError("offline acquisition requires a validated normalized binomial")

        groups = tuple(
            tuple(aspect for aspect in policy_group if aspect in missing)
            for policy_group in policy.search_groups
            if any(aspect in missing for aspect in policy_group)
        )[: policy.max_searches]
        if any(len(group) > policy.max_aspects_per_search_group for group in groups):
            raise ValueError("acquisition group exceeds the selected policy")

        selected: dict[str, TrustedPageEvidence] = {}
        provider_failures: list[Exception] = []
        completed_groups = 0
        for group in groups:
            terms = aspect_query_terms([aspect.value for aspect in group])
            query = " ".join(
                [identity.normalized_binomial, *terms, "botanical care evidence"]
            )
            try:
                candidates = await self.search.search(
                    query,
                    allowed_domains=sorted(self.trusted_sources.approved_domains),
                )
            except (ProviderError, AllProvidersFailedError, TimeoutError) as exc:
                provider_failures.append(exc)
                logger.warning(
                    "enrichment_search_group_failed",
                    extra={
                        "ctx_group_size": len(group),
                        "ctx_completed_groups": completed_groups,
                    },
                )
                continue
            completed_groups += 1
            trusted = self.trusted_sources.filter(candidates)
            for page in await self.page_fetcher.fetch_all(trusted, limit=3):
                if not (page.has_fetched_content and page.fetch_status == "fetched"):
                    continue
                if page.evidence_text.strip():
                    selected.setdefault(page.result.url, page)

        if not selected and provider_failures and len(provider_failures) == len(groups):
            raise provider_failures[-1]

        return OfflineAcquisitionResult(
            searched_groups=groups,
            evidence=tuple(selected.values()),
        )


__all__ = ["OfflineAcquisitionResult", "OfflineEnrichmentAcquisitionService"]
