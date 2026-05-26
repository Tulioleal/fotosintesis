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
    taxonomic_status: str | None = None
    synonyms: list[str] = field(default_factory=list)
    genus: str | None = None
    family: str | None = None
    species: str | None = None
    matched: bool = False


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
        synonyms = []
        if payload.get("synonym") and payload.get("scientificName") != accepted_name:
            synonyms.append(payload.get("scientificName"))

        return GbifTaxonomy(
            key=usage_key,
            accepted_key=accepted_key,
            accepted_scientific_name=accepted_name,
            taxonomic_status=payload.get("status"),
            synonyms=synonyms,
            genus=payload.get("genus"),
            family=payload.get("family"),
            species=payload.get("species"),
            matched=True,
        )
