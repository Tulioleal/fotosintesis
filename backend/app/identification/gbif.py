import asyncio
import json
from dataclasses import dataclass, field
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class GbifTaxonomy:
    key: int | None = None
    accepted_key: int | None = None
    accepted_scientific_name: str | None = None
    binomial_name: str | None = None
    taxonomic_status: str | None = None
    synonyms: list[str] = field(default_factory=list)
    genus: str | None = None
    family: str | None = None
    species: str | None = None
    matched: bool = False

    def __post_init__(self) -> None:
        if self.binomial_name or not self.genus or not self.species:
            return

        species = self.species.strip()
        genus = self.genus.strip()
        if not species or not genus:
            return

        if species.startswith(f"{genus} "):
            object.__setattr__(self, "binomial_name", species)
            return

        object.__setattr__(self, "binomial_name", f"{genus} {species}")

    @property
    def has_canonical_identity(self) -> bool:
        if not self.matched or not self.binomial_name:
            return False

        try:
            from app.enrichment.identity import CanonicalSpeciesIdentity

            CanonicalSpeciesIdentity(
                accepted_gbif_key=self.accepted_key,
                normalized_binomial=self.binomial_name,
                taxonomy_validated=True,
            )
        except ValueError:
            return False

        return True


class GbifClient:
    base_url = "https://api.gbif.org/v1/species/match"

    async def match_name(self, scientific_name: str) -> GbifTaxonomy:
        return await asyncio.to_thread(self._match_name_sync, scientific_name)

    def _match_name_sync(self, scientific_name: str) -> GbifTaxonomy:
        query = urlencode({"name": scientific_name, "rank": "SPECIES", "strict": "false"})
        try:
            with urlopen(f"{self.base_url}?{query}", timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return GbifTaxonomy()

        usage_key = payload.get("usageKey")
        confidence = int(payload.get("confidence") or 0)
        if not usage_key or payload.get("matchType") == "NONE" or confidence < 80:
            return GbifTaxonomy()

        accepted_key = payload.get("acceptedUsageKey") or usage_key
        accepted_name = payload.get("acceptedScientificName") or payload.get("scientificName")
        canonical_name = payload.get("canonicalName")
        synonyms = []
        if payload.get("synonym") and payload.get("scientificName") != accepted_name:
            synonyms.append(payload.get("scientificName"))

        return GbifTaxonomy(
            key=usage_key,
            accepted_key=accepted_key,
            accepted_scientific_name=accepted_name,
            binomial_name=(canonical_name.strip() or None) if isinstance(canonical_name, str) else None,
            taxonomic_status=payload.get("status"),
            synonyms=synonyms,
            genus=payload.get("genus"),
            family=payload.get("family"),
            species=payload.get("species"),
            matched=True,
        )
