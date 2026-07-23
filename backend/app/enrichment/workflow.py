from __future__ import annotations

from dataclasses import dataclass

from app.assistant.aspects.registry import REQUIRED_ASPECT_METADATA
from app.assistant.care_contracts import RequiredAspect


@dataclass(frozen=True)
class EnrichmentWorkflowAspects:
    required_aspects: frozenset[RequiredAspect]
    local_covered_aspects: frozenset[RequiredAspect]
    acquisition_aspects: frozenset[RequiredAspect]
    final_covered_aspects: frozenset[RequiredAspect]
    final_missing_aspects: frozenset[RequiredAspect]

    def __post_init__(self) -> None:
        if not self.required_aspects:
            raise ValueError("required_aspects must not be empty")
        if any(aspect not in REQUIRED_ASPECT_METADATA for aspect in self.required_aspects):
            raise ValueError("required_aspects must belong to the canonical registry")
        if not self.local_covered_aspects <= self.required_aspects:
            raise ValueError("local_covered_aspects must be required aspects")
        if self.acquisition_aspects != self.required_aspects - self.local_covered_aspects:
            raise ValueError("acquisition_aspects must be required minus local coverage")
        if not self.final_covered_aspects <= self.required_aspects:
            raise ValueError("final_covered_aspects must be required aspects")
        if self.final_missing_aspects != self.required_aspects - self.final_covered_aspects:
            raise ValueError("final_missing_aspects must be required minus final coverage")

    @classmethod
    def from_coverage(
        cls,
        *,
        required_aspects: frozenset[RequiredAspect],
        local_covered_aspects: frozenset[RequiredAspect],
        final_covered_aspects: frozenset[RequiredAspect] | None = None,
    ) -> EnrichmentWorkflowAspects:
        final = local_covered_aspects if final_covered_aspects is None else final_covered_aspects
        return cls(
            required_aspects=required_aspects,
            local_covered_aspects=local_covered_aspects,
            acquisition_aspects=required_aspects - local_covered_aspects,
            final_covered_aspects=final,
            final_missing_aspects=required_aspects - final,
        )


__all__ = ["EnrichmentWorkflowAspects"]
