from __future__ import annotations

from dataclasses import InitVar, dataclass


def _normalize_binomial(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    words = value.split()
    if len(words) != 2:
        return None
    valid_words = all(
        part.isalpha()
        or "-" in part
        and all(piece.isalpha() for piece in part.split("-"))
        for part in words
    )
    if not valid_words:
        return None
    genus, species = words
    return f"{genus[0].upper()}{genus[1:].lower()} {species.lower()}"


@dataclass(frozen=True)
class CanonicalSpeciesIdentity:
    accepted_gbif_key: int | None
    normalized_binomial: str
    taxonomy_validated: InitVar[bool]

    def __post_init__(self, taxonomy_validated: bool) -> None:
        if not taxonomy_validated:
            raise ValueError("canonical species identity requires taxonomy validation")

        if isinstance(self.accepted_gbif_key, bool) or (
            self.accepted_gbif_key is not None
            and self.accepted_gbif_key <= 0
        ):
            raise ValueError("accepted_gbif_key must be a positive integer")

        normalized = _normalize_binomial(self.normalized_binomial)
        if normalized is None:
            raise ValueError(
                "canonical species identity requires a validated normalized binomial"
            )

        object.__setattr__(self, "normalized_binomial", normalized)

    @property
    def key(self) -> str:
        if self.accepted_gbif_key is not None:
            return (
                f"gbif:{self.accepted_gbif_key}"
                f"|binomial:{self.normalized_binomial}"
            )
        return f"binomial:{self.normalized_binomial}"


__all__ = ["CanonicalSpeciesIdentity"]
