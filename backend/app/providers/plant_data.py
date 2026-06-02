from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.providers.interfaces import PlantDataProvider
from app.providers.types import PlantDataResult


class PlantDataProviderError(RuntimeError):
    pass


class TreflePlantDataProvider(PlantDataProvider):
    provider_name = "trefle"

    def __init__(self, *, api_key: str, base_url: str = "https://trefle.io/api/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        data = await _fetch_json(
            f"{self.base_url}/plants/search?"
            + urlencode({"token": self.api_key, "q": scientific_name})
        )
        item = _exact_item(data.get("data"), scientific_name)
        if not item:
            return None
        fields = {
            "description": item.get("description"),
            "family": item.get("family"),
            "genus": item.get("genus"),
            "rank": item.get("rank"),
            "year": item.get("year"),
            "author": item.get("author"),
            "bibliography": item.get("bibliography"),
            "common_name": item.get("common_name"),
        }
        return PlantDataResult(
            provider=self.provider_name,
            scientific_name=str(item.get("scientific_name") or scientific_name),
            common_name=item.get("common_name"),
            family=item.get("family"),
            genus=item.get("genus"),
            rank=item.get("rank"),
            fields={key: value for key, value in fields.items() if value},
            source_url=str(item.get("links", {}).get("self") or "https://trefle.io"),
        )


class PerenualPlantDataProvider(PlantDataProvider):
    provider_name = "perenual"

    def __init__(self, *, api_key: str, base_url: str = "https://perenual.com/api") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        data = await _fetch_json(
            f"{self.base_url}/species-list?" + urlencode({"key": self.api_key, "q": scientific_name})
        )
        print(data)
        item = _exact_item(data.get("data"), scientific_name)
        if not item:
            return None
        detail = item
        species_id = item.get("id")
        if species_id is not None:
            try:
                detail = await _fetch_json(
                    f"{self.base_url}/species/details/{species_id}?" + urlencode({"key": self.api_key})
                )
            except Exception:
                detail = item
        fields = {
            "watering": detail.get("watering"),
            "sunlight": detail.get("sunlight"),
            "soil": detail.get("soil"),
            "maintenance": detail.get("maintenance"),
            "pests": detail.get("pest_susceptibility"),
            "care": _care_guides(detail),
        }
        return PlantDataResult(
            provider=self.provider_name,
            scientific_name=scientific_name,
            common_name=_first(detail.get("common_name")),
            fields={key: value for key, value in fields.items() if value},
            source_url="https://perenual.com",
        )


async def _fetch_json(url: str) -> dict[str, Any]:
    import asyncio

    def fetch() -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "FotosintesisBot/1.0 (+plant data lookup)"})
        with urlopen(request, timeout=10) as response:
            payload = response.read(1_000_000)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise PlantDataProviderError("plant-data provider returned non-object JSON")
        return data

    return await asyncio.to_thread(fetch)


def _exact_item(items: Any, scientific_name: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    expected = scientific_name.casefold().strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        names = [item.get("scientific_name"), item.get("latin_name")]
        if any(str(name).casefold().strip() == expected for name in names if name):
            return item
    return None


def _care_guides(data: dict[str, Any]) -> str | None:
    guides = data.get("care-guides") or data.get("care_guides")
    if isinstance(guides, str):
        return guides
    if isinstance(guides, list):
        return "; ".join(str(guide) for guide in guides if str(guide).strip()) or None
    if isinstance(guides, dict):
        return "; ".join(str(value) for value in guides.values() if str(value).strip()) or None
    return None


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None
