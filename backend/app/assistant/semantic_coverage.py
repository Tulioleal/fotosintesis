from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.assistant.aspect_metadata import metadata_for_aspect
from app.assistant.care_contracts import EvidenceValidationResult, RequiredAspect
from app.assistant.graph_shared import AnswerabilityResult
from app.enrichment.workflow import EnrichmentWorkflowAspects

AnswerabilityStatus = Literal["full", "partial", "insufficient", "contradictory"]


@dataclass(frozen=True)
class CoverageThresholds:
    default: float
    safety: float
    strong_full: float = 0.30


@dataclass(frozen=True)
class SemanticSourceEvidence:
    """One supplied evidence package keeping source text bound to its metadata.

    ``metadata`` must carry a ``url`` key; the binding layer uses that URL to
    attach judge support to exactly one supplied source so a support item can
    never cite an undifferentiated concatenated text blob.
    """

    text: str
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class SemanticEvidence:
    """Source-separated evidence with caller-scoped trust eligibility.

    ``eligible_validation_statuses`` is a closed per-caller set: production
    enrichment and normal assistant RAG construct evidence eligible only for
    ``trusted``, and only the assistant trusted-first fallback path may
    construct evidence eligible for ``{"trusted", "external_fallback"}``.
    ``external_fallback`` is never globally treated as trusted.
    """

    sources: tuple[SemanticSourceEvidence, ...]
    eligible_validation_statuses: frozenset[str] = frozenset({"trusted"})

    @property
    def combined_text(self) -> str:
        return " ".join(
            source.text for source in self.sources if source.text.strip()
        )


@dataclass(frozen=True)
class SemanticJudgeRequest:
    required_aspects: tuple[RequiredAspect, ...]
    local_evidence: SemanticEvidence
    acquired_evidence: SemanticEvidence | None = None
    local_answerability: AnswerabilityResult | None = None


@dataclass(frozen=True)
class LocalCoverage:
    aspects: EnrichmentWorkflowAspects
    answerability: AnswerabilityResult
    evidence: SemanticEvidence

    @property
    def required_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.required_aspects

    @property
    def local_covered_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.local_covered_aspects

    @property
    def acquisition_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.acquisition_aspects

    @property
    def initial_missing_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.acquisition_aspects


@dataclass(frozen=True)
class FinalCoverage:
    aspects: EnrichmentWorkflowAspects
    answerability: AnswerabilityResult
    acquisition_used: bool

    @property
    def required_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.required_aspects

    @property
    def local_covered_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.local_covered_aspects

    @property
    def acquisition_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.acquisition_aspects

    @property
    def final_covered_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.final_covered_aspects

    @property
    def final_missing_aspects(self) -> frozenset[RequiredAspect]:
        return self.aspects.final_missing_aspects


LocalEvidenceRetriever = Callable[[tuple[RequiredAspect, ...]], Awaitable[SemanticEvidence]]
SemanticJudge = Callable[[SemanticJudgeRequest], Awaitable[Any]]


class SemanticCoverageService:
    """Normalize semantic answerability and calculate explicit aspect coverage."""

    async def evaluate_local(
        self,
        *,
        required_aspects: Sequence[RequiredAspect | str],
        retrieve: LocalEvidenceRetriever,
        judge: SemanticJudge,
        thresholds: CoverageThresholds,
    ) -> LocalCoverage:
        required = self.canonical_aspects(required_aspects)
        evidence = await retrieve(required)
        raw_result = await judge(
            SemanticJudgeRequest(required_aspects=required, local_evidence=evidence)
        )
        answerability = self.normalized_coverage(
            raw_result,
            required_aspects=required,
            thresholds=thresholds,
            evidence=evidence,
        )
        covered = self._covered_members(answerability, required)
        aspects = EnrichmentWorkflowAspects.from_coverage(
            required_aspects=frozenset(required),
            local_covered_aspects=frozenset(covered),
        )
        return LocalCoverage(
            aspects=aspects,
            answerability=answerability,
            evidence=evidence,
        )

    async def evaluate_final(
        self,
        *,
        local: LocalCoverage,
        acquired_evidence: SemanticEvidence | None,
        judge: SemanticJudge,
        thresholds: CoverageThresholds,
    ) -> FinalCoverage:
        if not local.acquisition_aspects:
            return FinalCoverage(
                aspects=local.aspects,
                answerability=local.answerability,
                acquisition_used=False,
            )

        required = self.canonical_aspects(local.required_aspects)

        raw_result = await judge(
            SemanticJudgeRequest(
                required_aspects=required,
                local_evidence=local.evidence,
                acquired_evidence=acquired_evidence,
                local_answerability=local.answerability,
            )
        )
        answerability = self.normalized_coverage(
            raw_result,
            required_aspects=required,
            thresholds=thresholds,
            evidence=self._combined_evidence(local.evidence, acquired_evidence),
        )
        covered = self._covered_members(answerability, required)
        aspects = EnrichmentWorkflowAspects.from_coverage(
            required_aspects=local.required_aspects,
            local_covered_aspects=local.local_covered_aspects,
            final_covered_aspects=frozenset(covered),
        )
        return FinalCoverage(
            aspects=aspects,
            answerability=answerability,
            acquisition_used=True,
        )

    def canonical_aspects(
        self, aspects: Iterable[RequiredAspect | str]
    ) -> tuple[RequiredAspect, ...]:
        values: set[RequiredAspect] = set()
        for value in aspects:
            try:
                aspect = value if isinstance(value, RequiredAspect) else RequiredAspect(value)
            except ValueError as exc:
                raise ValueError(f"unknown required aspect: {value}") from exc
            if metadata_for_aspect(aspect) is None:
                raise ValueError(f"required aspect is absent from the canonical registry: {value}")
            values.add(aspect)
        if not values:
            raise ValueError("at least one required aspect is required")
        return tuple(aspect for aspect in RequiredAspect if aspect in values)

    def map_judge_result(self, result: Any) -> AnswerabilityResult:
        score = self._float_or_zero(self._value(result, "score", 0.0))
        confidence = max(
            0.0,
            min(1.0, self._float_or_zero(self._value(result, "confidence", score))),
        )
        reasons = [
            str(reason)
            for reason in self._string_sequence(self._value(result, "reasons", []))
            if str(reason).strip()
        ]
        raw_status = self._value(result, "status")
        status = self._status(raw_status)

        if status is None:
            if raw_status is not None:
                status = "insufficient"
            else:
                status = (
                    "full"
                    if bool(self._value(result, "passed", False))
                    else "insufficient"
                )
        answerable = status == "full"
        if self._has_value(result, "answerable"):
            answerable = bool(self._value(result, "answerable", False))
        return AnswerabilityResult(
            status=status,
            answerable=answerable,
            covered_aspects=self._string_list(self._value(result, "covered_aspects", [])),
            missing_aspects=(
                []
                if status == "full"
                else self._string_list(self._value(result, "missing_aspects", []))
            ),
            source_support=self._dict_list(self._value(result, "source_support", [])),
            contradictions=self._dict_list(self._value(result, "contradictions", [])),
            reason=(
                "; ".join(reasons) if reasons else "answerability judge did not provide a reason"
            ),
            confidence=confidence,
        )

    def normalize_answerability(
        self,
        result: AnswerabilityResult,
        *,
        requested_aspects: Sequence[str],
    ) -> AnswerabilityResult:
        if result.answerable and result.status == "insufficient":
            result = AnswerabilityResult(
                status="full",
                answerable=True,
                covered_aspects=result.covered_aspects,
                missing_aspects=result.missing_aspects,
                source_support=result.source_support,
                contradictions=result.contradictions,
                reason=result.reason,
                confidence=result.confidence,
            )
        requested = [aspect for aspect in requested_aspects if aspect]
        covered = [aspect for aspect in result.covered_aspects if aspect in requested]
        missing = [aspect for aspect in requested if aspect not in covered]
        contradictions = [item for item in result.contradictions if self.valid_contradiction(item)]
        support = self.normalized_source_support(result.source_support, allowed_aspects=covered)

        if result.status == "full":
            if not requested:
                requested = [RequiredAspect.general_care_summary.value]
                covered = requested if result.answerable else covered
                missing = [] if result.answerable else requested
            if result.answerable and not covered:
                covered = list(requested)
                missing = []
                support = self.normalized_source_support(
                    result.source_support, allowed_aspects=covered
                )
            if set(covered) >= set(requested) and support:
                return AnswerabilityResult(
                    "full",
                    True,
                    covered,
                    [],
                    support,
                    contradictions,
                    result.reason,
                    result.confidence,
                )
            if covered and support:
                return AnswerabilityResult(
                    "partial",
                    False,
                    covered,
                    missing,
                    support,
                    contradictions,
                    result.reason,
                    result.confidence,
                )
            return AnswerabilityResult(
                "insufficient",
                False,
                [],
                requested,
                reason=result.reason,
                confidence=result.confidence,
            )
        if result.status == "partial":
            if set(covered) >= set(requested) and support and not contradictions:
                return AnswerabilityResult(
                    "full",
                    True,
                    covered,
                    [],
                    support,
                    contradictions,
                    result.reason,
                    result.confidence,
                )
            if covered and support:
                return AnswerabilityResult(
                    "partial",
                    False,
                    covered,
                    missing,
                    support,
                    contradictions,
                    result.reason,
                    result.confidence,
                )
            return AnswerabilityResult(
                "insufficient",
                False,
                [],
                requested,
                reason=result.reason,
                confidence=result.confidence,
            )
        if result.status == "contradictory":
            if contradictions:
                return AnswerabilityResult(
                    "contradictory",
                    False,
                    covered,
                    missing or requested,
                    support,
                    contradictions,
                    result.reason,
                    result.confidence,
                )
            return AnswerabilityResult(
                "insufficient",
                False,
                covered,
                missing or requested,
                support,
                reason=result.reason or "contradictory answerability result lacked source URLs",
                confidence=result.confidence,
            )
        return AnswerabilityResult(
            "insufficient",
            False,
            covered,
            missing or requested,
            support,
            contradictions,
            result.reason,
            result.confidence,
        )

    def normalized_coverage(
        self,
        result: Any,
        *,
        required_aspects: Sequence[RequiredAspect | str],
        thresholds: CoverageThresholds,
        evidence: SemanticEvidence | None = None,
    ) -> AnswerabilityResult:
        required = self.canonical_aspects(required_aspects)
        mapped = (
            result if isinstance(result, AnswerabilityResult) else self.map_judge_result(result)
        )
        if evidence is not None:
            mapped = self._bind_source_support(mapped, evidence=evidence, thresholds=thresholds)
        normalized = self.normalize_answerability(
            mapped,
            requested_aspects=[aspect.value for aspect in required],
        )
        validation = self.validate_evidence(
            normalized,
            requested_aspects=required,
            thresholds=thresholds,
            require_direct_support=evidence is not None,
        )
        covered = [aspect.value for aspect in validation.covered_aspects]
        missing = [aspect.value for aspect in validation.missing_aspects]
        support = self.normalized_source_support(
            normalized.source_support,
            allowed_aspects=covered,
        )
        if normalized.status == "contradictory":
            status: AnswerabilityStatus = "contradictory"
            covered: list[str] = []
            missing = [aspect.value for aspect in required]
            support: list[dict[str, object]] = []
        elif not covered:
            status = "insufficient"
        elif not missing:
            status = "full"
        else:
            status = "partial"
        return AnswerabilityResult(
            status=status,
            answerable=status == "full",
            covered_aspects=covered,
            missing_aspects=missing,
            source_support=support,
            contradictions=normalized.contradictions,
            reason=normalized.reason,
            confidence=normalized.confidence,
        )

    def validate_evidence(
        self,
        semantic_result: AnswerabilityResult,
        *,
        requested_aspects: Sequence[RequiredAspect],
        thresholds: CoverageThresholds,
        require_direct_support: bool = False,
    ) -> EvidenceValidationResult:
        requested = list(requested_aspects)
        requested_values = [aspect.value for aspect in requested]
        candidate_values = (
            requested_values
            if semantic_result.status == "full" and semantic_result.answerable
            else semantic_result.covered_aspects
        )
        covered: list[RequiredAspect] = []
        for aspect in requested:
            if aspect.value not in candidate_values:
                continue
            if (require_direct_support or self._is_safety_sensitive(aspect)) and not (
                self._has_direct_support(semantic_result, aspect)
            ):
                continue
            threshold = self.validation_threshold_for_aspect(
                aspect,
                semantic_result,
                requested_values,
                thresholds=thresholds,
            )
            if semantic_result.confidence >= threshold:
                covered.append(aspect)
        missing = [aspect for aspect in requested if aspect not in covered]
        return EvidenceValidationResult(
            answerable=not missing and bool(covered),
            covered_aspects=covered,
            missing_aspects=missing,
            unsupported_claims_risk=bool(missing),
            reason=semantic_result.reason,
            confidence=semantic_result.confidence,
        )

    def validation_threshold_for_aspect(
        self,
        aspect: RequiredAspect,
        semantic_result: AnswerabilityResult,
        requested_aspects: Sequence[str],
        *,
        thresholds: CoverageThresholds,
    ) -> float:
        if self._is_safety_sensitive(aspect):
            return thresholds.safety
        if self.is_strong_full_support(semantic_result, requested_aspects):
            return thresholds.strong_full
        return thresholds.default

    @staticmethod
    def is_strong_full_support(
        semantic_result: AnswerabilityResult, requested_aspects: Sequence[str]
    ) -> bool:
        return (
            semantic_result.status == "full"
            and semantic_result.answerable
            and bool(semantic_result.source_support)
            and not semantic_result.contradictions
            and all(aspect in set(semantic_result.covered_aspects) for aspect in requested_aspects)
        )

    def normalized_source_support(
        self,
        items: Sequence[dict[str, object]],
        *,
        allowed_aspects: Sequence[str],
    ) -> list[dict[str, object]]:
        allowed = set(allowed_aspects)
        normalized_items: list[dict[str, object]] = []
        for item in items:
            if not self.valid_source_support(item, allowed_aspects):
                continue
            aspects = item.get("covered_aspects")
            if not isinstance(aspects, list):
                continue
            normalized_aspects: list[str] = []
            for aspect in aspects:
                if not isinstance(aspect, str) or aspect not in allowed:
                    continue
                if aspect not in normalized_aspects:
                    normalized_aspects.append(aspect)
            if not normalized_aspects:
                continue
            normalized_item = dict(item)
            normalized_item["covered_aspects"] = normalized_aspects
            normalized_items.append(normalized_item)
        return normalized_items

    @staticmethod
    def valid_source_support(item: dict[str, object], requested_aspects: Sequence[str]) -> bool:
        urls = item.get("source_urls")
        aspects = item.get("covered_aspects")
        quote = item.get("evidence_quote")
        non_empty_urls = (
            [url for url in urls if isinstance(url, str) and url.strip()]
            if isinstance(urls, list)
            else []
        )
        return (
            isinstance(item.get("claim"), str)
            and bool(str(item.get("claim")).strip())
            and isinstance(quote, str)
            and bool(quote.strip())
            and isinstance(urls, list)
            and len(urls) == 1
            and len(non_empty_urls) == 1
            and isinstance(aspects, list)
            and any(isinstance(aspect, str) and aspect in requested_aspects for aspect in aspects)
        )

    @staticmethod
    def valid_contradiction(item: dict[str, object]) -> bool:
        left = item.get("source_a_urls")
        right = item.get("source_b_urls")
        return (
            isinstance(item.get("claim_a"), str)
            and isinstance(item.get("claim_b"), str)
            and isinstance(left, list)
            and isinstance(right, list)
            and any(isinstance(url, str) and url.strip() for url in left)
            and any(isinstance(url, str) and url.strip() for url in right)
        )

    @staticmethod
    def _covered_members(
        result: AnswerabilityResult, required: tuple[RequiredAspect, ...]
    ) -> tuple[RequiredAspect, ...]:
        covered = set(result.covered_aspects)
        return tuple(aspect for aspect in required if aspect.value in covered)

    @staticmethod
    def _has_direct_support(result: AnswerabilityResult, aspect: RequiredAspect) -> bool:
        return any(
            aspect.value in item.get("covered_aspects", [])
            for item in result.source_support
            if isinstance(item.get("covered_aspects"), list)
        )

    @classmethod
    def _bind_source_support(
        cls,
        result: AnswerabilityResult,
        *,
        evidence: SemanticEvidence,
        thresholds: CoverageThresholds,
    ) -> AnswerabilityResult:
        packages_by_url: dict[str, list[SemanticSourceEvidence]] = {}
        for package in evidence.sources:
            url = str(package.metadata.get("url") or "").strip()
            if url:
                packages_by_url.setdefault(url, []).append(package)

        bound: list[dict[str, object]] = []
        for item in result.source_support:
            urls = item.get("source_urls")
            quote = item.get("evidence_quote")
            aspects = item.get("covered_aspects")
            claim = item.get("claim")
            if (
                not isinstance(urls, list)
                or not isinstance(quote, str)
                or not quote.strip()
                or not isinstance(aspects, list)
                or not isinstance(claim, str)
                or not claim.strip()
            ):
                continue
            matched_urls = [
                url.strip() for url in urls if isinstance(url, str) and url.strip()
            ]
            if len(urls) != 1 or len(matched_urls) != 1:
                continue
            url = matched_urls[0]
            packages = packages_by_url.get(url)
            if packages is None or not cls._sources_are_eligible(
                packages, evidence.eligible_validation_statuses
            ):
                continue
            confidence = cls._float_or_zero(item.get("confidence"))
            supported_aspects: list[str] = []
            for aspect in aspects:
                if not isinstance(aspect, str):
                    continue
                try:
                    required_aspect = RequiredAspect(aspect)
                except ValueError:
                    continue
                if (
                    cls._is_safety_sensitive(required_aspect)
                    and confidence < thresholds.safety
                ):
                    continue
                supported_aspects.append(aspect)
            if not supported_aspects:
                continue
            normalized_item = dict(item)
            normalized_item["source_urls"] = [url]
            normalized_item["covered_aspects"] = list(dict.fromkeys(supported_aspects))
            bound.append(normalized_item)
        return AnswerabilityResult(
            status=result.status,
            answerable=result.answerable,
            covered_aspects=result.covered_aspects,
            missing_aspects=result.missing_aspects,
            source_support=bound,
            contradictions=result.contradictions,
            reason=result.reason,
            confidence=result.confidence,
        )

    @staticmethod
    def _sources_are_eligible(
        packages: Sequence[SemanticSourceEvidence],
        eligible: frozenset[str],
    ) -> bool:
        """Fail closed: every package matching the URL must carry an explicit
        validation status inside the caller's closed eligibility set. Missing,
        blank, unknown, or caller-ineligible statuses reject the URL."""
        if not packages:
            return False
        for package in packages:
            status = package.metadata.get("validation_status")
            if not isinstance(status, str) or not status.strip():
                return False
            if status.strip().casefold() not in eligible:
                return False
        return True

    @staticmethod
    def _combined_evidence(
        local: SemanticEvidence, acquired: SemanticEvidence | None
    ) -> SemanticEvidence:
        if acquired is None:
            return local
        return SemanticEvidence(
            sources=local.sources + acquired.sources,
            eligible_validation_statuses=(
                local.eligible_validation_statuses
                & acquired.eligible_validation_statuses
            ),
        )

    @staticmethod
    def _is_safety_sensitive(aspect: RequiredAspect) -> bool:
        metadata = metadata_for_aspect(aspect)
        return bool(metadata and metadata.safety_sensitive)

    @staticmethod
    def _status(value: Any) -> AnswerabilityStatus | None:
        status = str(value or "").strip().lower()
        if status in {"full", "partial", "insufficient", "contradictory"}:
            return status  # type: ignore[return-value]
        return None

    @staticmethod
    def _string_sequence(value: Any) -> list[Any]:
        return list(value) if isinstance(value, list | tuple | set) else []

    @classmethod
    def _string_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(item) for item in cls._string_sequence(value) if str(item).strip()]

    @staticmethod
    def _dict_list(value: Any) -> list[dict[str, object]]:
        if not isinstance(value, list | tuple):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    @staticmethod
    def _float_or_zero(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _value(result: Any, name: str, default: Any = None) -> Any:
        if isinstance(result, Mapping):
            return result.get(name, default)
        return getattr(result, name, default)

    @staticmethod
    def _has_value(result: Any, name: str) -> bool:
        return name in result if isinstance(result, Mapping) else hasattr(result, name)


semantic_coverage_service = SemanticCoverageService()


__all__ = [
    "CoverageThresholds",
    "FinalCoverage",
    "LocalCoverage",
    "LocalEvidenceRetriever",
    "SemanticCoverageService",
    "SemanticEvidence",
    "SemanticJudge",
    "SemanticJudgeRequest",
    "SemanticSourceEvidence",
    "semantic_coverage_service",
]
