import asyncio
import json
from dataclasses import dataclass, field
from time import perf_counter, sleep
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.settings import get_settings
from app.observability.logging import get_logger


logger = get_logger(__name__)


class ProviderLookupError(RuntimeError):
    """Raised when an external provider lookup fails in a retryable way."""

    def __init__(
        self,
        message: str,
        *,
        cause_type: str | None = None,
        attempts: int | None = None,
        latency_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.cause_type = cause_type
        self.attempts = attempts
        self.latency_seconds = latency_seconds


@dataclass(frozen=True)
class GbifTaxonomy:
    key: int | None = None
    accepted_key: int | None = None
    accepted_scientific_name: str | None = None
    binomial_name: str | None = None
    taxonomic_status: str | None = None
    rank: str | None = None
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
    def __init__(
        self,
        base_url: str | None = None,
        *,
        match_attempts: int = 3,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        self.base_url = base_url or get_settings().gbif_base_url
        self.match_attempts = max(1, match_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    async def match_name(self, scientific_name: str) -> GbifTaxonomy:
        return await asyncio.to_thread(self._match_name_sync, scientific_name)

    async def suggest(self, query: str, limit: int = 8) -> list[GbifTaxonomy]:
        return await asyncio.to_thread(self._suggest_sync, query, limit)

    def _suggest_sync(self, query: str, limit: int) -> list[GbifTaxonomy]:
        base = self.base_url.rsplit("/", 1)[0]
        suggest_url = f"{base}/suggest"
        params = {"q": query, "limit": max(1, min(limit, 20))}
        try:
            with urlopen(f"{suggest_url}?{urlencode(params)}", timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderLookupError(
                "GBIF name lookup failed; retry the external expansion."
            ) from exc

        if not isinstance(payload, list):
            return []

        accepted: list[GbifTaxonomy] = []
        other: list[GbifTaxonomy] = []
        for entry in payload:
            taxonomy = self._normalize_suggest_entry(entry)
            if taxonomy is None:
                continue
            if taxonomy.taxonomic_status == "ACCEPTED" and taxonomy.matched:
                accepted.append(taxonomy)
            else:
                other.append(taxonomy)

        # Prioritize accepted species-level results, then the rest.
        ranked = accepted + other
        return ranked[:limit]

    def _match_name_sync(self, scientific_name: str) -> GbifTaxonomy:
        query = urlencode({"name": scientific_name, "rank": "SPECIES", "strict": "false"})
        started = perf_counter()
        for attempt in range(1, self.match_attempts + 1):
            try:
                with urlopen(f"{self.base_url}?{query}", timeout=4) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if attempt > 1:
                    logger.info(
                        "gbif_match_lookup_recovered",
                        extra={
                            "ctx_attempts": attempt,
                            "ctx_latency_seconds": round(perf_counter() - started, 6),
                        },
                    )
                break
            except Exception as exc:
                if attempt >= self.match_attempts:
                    raise ProviderLookupError(
                        "GBIF name lookup failed; retry taxonomy validation.",
                        cause_type=type(exc).__name__,
                        attempts=attempt,
                        latency_seconds=perf_counter() - started,
                    ) from exc
                sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))

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

    def _normalize_suggest_entry(self, entry: dict) -> GbifTaxonomy | None:
        """Normalize a single GBIF name-suggest entry into a bounded taxonomy."""
        if not isinstance(entry, dict):
            return None
        key = entry.get("key")
        if key is None:
            return None

        canonical = entry.get("canonicalName")
        scientific = entry.get("scientificName")
        accepted_name = entry.get("acceptedName") or scientific or canonical
        accepted_key = entry.get("acceptedKey") or key

        synonyms: list[str] = []
        if scientific and accepted_name and scientific != accepted_name:
            synonyms.append(scientific)

        status = entry.get("status")
        rank = entry.get("rank")

        return GbifTaxonomy(
            key=key,
            accepted_key=accepted_key,
            accepted_scientific_name=accepted_name,
            binomial_name=(canonical.strip() or None) if isinstance(canonical, str) else None,
            taxonomic_status=status,
            synonyms=synonyms,
            genus=entry.get("genus"),
            family=entry.get("family"),
            species=entry.get("species"),
            rank=rank,
            matched=True,
        )


__all__ = ["GbifClient", "GbifTaxonomy", "ProviderLookupError"]
