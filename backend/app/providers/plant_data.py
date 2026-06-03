from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
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
        binomial_name = _binomial_name(scientific_name)
        data = await _fetch_json(
            f"{self.base_url}/plants/search?"
            + urlencode({"token": self.api_key, "q": binomial_name})
        )
        item = _best_trefle_item(data.get("data"), binomial_name)
        if not item:
            return None
        detail = await self._fetch_detail(item)
        source_url = _absolute_trefle_url(
            str(detail.get("links", {}).get("self") or item.get("links", {}).get("self") or ""),
            self.base_url,
        )
        fields = {
            "description": _trefle_description(detail),
            "year": detail.get("year"),
            "author": detail.get("author"),
            "bibliography": detail.get("bibliography"),
            "family_common_name": detail.get("family_common_name"),
            "observations": detail.get("observations"),
            "vegetable": detail.get("vegetable"),
            "genus": detail.get("genus"),
            "family": detail.get("family"),
            "duration": detail.get("duration"),
            "edible_part": detail.get("edible_part"),
            "edible": detail.get("edible"),
            "distribution": detail.get("distribution"),
            "distributions": detail.get("distributions"),
            "flower": detail.get("flower"),
            "foliage": detail.get("foliage"),
            "fruit_or_seed": detail.get("fruit_or_seed"),
            "sources": detail.get("sources"),
            "specifications": detail.get("specifications"),
            "growth": detail.get("growth"),
        }
        return PlantDataResult(
            provider=self.provider_name,
            scientific_name=str(detail.get("scientific_name") or binomial_name),
            common_name=detail.get("common_name"),
            family=detail.get("family"),
            genus=detail.get("genus"),
            rank=detail.get("rank"),
            fields={key: value for key, value in fields.items() if value},
            source_url=source_url or "https://trefle.io",
        )

    async def _fetch_detail(self, item: dict[str, Any]) -> dict[str, Any]:
        detail_url = item.get("links", {}).get("self")
        if not detail_url and item.get("slug"):
            detail_url = f"/api/v1/species/{item['slug']}"
        if not detail_url:
            return item
        data = await _fetch_json(
            _with_token(_absolute_trefle_url(str(detail_url), self.base_url), self.api_key)
        )
        detail = data.get("data")
        return detail if isinstance(detail, dict) else item


class PerenualPlantDataProvider(PlantDataProvider):
    provider_name = "perenual"

    def __init__(self, *, api_key: str, base_url: str = "https://perenual.com/api/v2") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        binomial_name = _binomial_name(scientific_name)
        data = await _fetch_json(
            f"{self.base_url}/species-list?" + urlencode({"key": self.api_key, "q": binomial_name})
        )
        item = _best_perenual_item(data.get("data"), binomial_name)
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
            "watering": {
                "general_benchmark": detail.get("watering_general_benchmark"),
                "description": detail.get("watering"),
            },
            "sunlight": detail.get("sunlight"),
            "soil": detail.get("soil"),
            "maintenance": detail.get("maintenance"),
            "pests": detail.get("pest_susceptibility"),
            "care": _care_guides(detail),
            "other_name": detail.get("other_name"),
            "family": detail.get("family"),
            "hybrid": detail.get("hybrid"),
            "authority": detail.get("authority"),
            "subspecies": detail.get("subspecies"),
            "cultivar": detail.get("cultivar"),
            "variety": detail.get("variety"),
            "species_epithet": detail.get("species_epithet"),
            "genus": detail.get("genus"),
            "origin": detail.get("origin"),
            "type": detail.get("type"),
            "dimensions": detail.get("dimensions"),
            "cycle": detail.get("cycle"),
            "attracts": detail.get("attracts"),
            "propagation": detail.get("propagation"),
            "hardiness": detail.get("hardiness"),
            "hardiness_location": detail.get("hardiness_location"),
            "plant_anatomy": detail.get("plant_anatomy"),
            "pruning_month": detail.get("pruning_month"),
            "pruning_count": detail.get("pruning_count"),
            "seeds": detail.get("seeds"),
            "care_guides": detail.get("care_guides"),
            "growth_rate": detail.get("growth_rate"),   
            "drought_tolerant": detail.get("drought_tolerant"),
            "salt_tolerant": detail.get("salt_tolerant"),
            "thorny": detail.get("thorny"),
            "invasive": detail.get("invasive"),
            "tropical": detail.get("tropical"),
            "indoor": detail.get("indoor"),
            "care_level": detail.get("care_level"),
            "pest_susceptibility": detail.get("pest_susceptibility"),
            "flowers": detail.get("flowers"),
            "flowering_season": detail.get("flowering_season"),
            "cones": detail.get("cones"),
            "fruits": detail.get("fruits"),
            "edible_fruit": detail.get("edible_fruit"),
            "harvest_season": detail.get("harvest_season"),
            "leaf": detail.get("leaf"),
            "edible_leaf": detail.get("edible_leaf"),
            "cuisine": detail.get("cuisine"),
            "medicinal": detail.get("medicinal"),
            "poisonous_to_humans": detail.get("poisonous_to_humans"),
            "poisonous_to_pets": detail.get("poisonous_to_pets"),
            "description": detail.get("description"),
            "default_image": detail.get("default_image")
        }
        return PlantDataResult(
            provider=self.provider_name,
            scientific_name=_first(detail.get("scientific_name")) or binomial_name,
            common_name=_first(detail.get("common_name")),
            family=detail.get("family"),
            genus=detail.get("genus"),
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

def _binomial_name(value: str) -> str:
    parts = value.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else value.strip()

def _exact_item(items: Any, binomial_name: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    expected = binomial_name.casefold().strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        names = [item.get("scientific_name"), item.get("latin_name")]
        if any(_binomial_name(str(name)).casefold().strip() == _binomial_name(expected) for name in _flatten(names) if name):
            return item
    return None


def _best_perenual_item(items: Any, binomial_name: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    candidates = [item for item in items if isinstance(item, dict)]
    if not candidates:
        return None
    exact = _exact_item(candidates, binomial_name)
    if exact:
        return exact

    expected_name = _normalized_name(binomial_name)
    for item in candidates:
        if any(
            _normalized_name(str(name)) == expected_name for name in _perenual_names(item) if name
        ):
            return item

    expected_binomial = _normalized_name(binomial_name)
    for item in candidates:
        if any(
            _normalized_name(str(name)) == expected_binomial
            for name in _perenual_names(item)
            if name
        ):
            return item
    return None


def _perenual_names(item: dict[str, Any]) -> list[Any]:
    return _flatten(
        [
            item.get("scientific_name"),
            item.get("latin_name"),
            item.get("other_name"),
            item.get("common_name"),
        ]
    )


def _flatten(values: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list | tuple | set):
            flattened.extend(value)
        else:
            flattened.append(value)
    return flattened


def _best_trefle_item(items: Any, scientific_name: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    candidates = [item for item in items if isinstance(item, dict)]
    if not candidates:
        return None
    exact = _exact_item(candidates, scientific_name)
    if exact:
        return exact
    expected_slug = _slug(scientific_name)
    for item in candidates:
        if str(item.get("slug") or "").casefold().strip() == expected_slug:
            return item
    expected_name = _normalized_name(scientific_name)
    for item in candidates:
        names = [
            item.get("scientific_name"),
            item.get("latin_name"),
            item.get("common_name"),
            *(_list_values(item.get("synonyms"))),
        ]
        if any(_normalized_name(str(name)) == expected_name for name in names if name):
            return item
    return None


def _list_values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _slug(value: str) -> str:
    return "-".join(part for part in _normalized_name(value).split() if part)


def _binomial_name(value: str) -> str:
    parts = value.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else value.strip()


def _normalized_name(value: str) -> str:
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in value).split()
    )


def _trefle_description(data: dict[str, Any]) -> Any:
    growth = data.get("growth")
    if isinstance(growth, dict) and growth.get("description"):
        return growth.get("description")
    return data.get("description") or data.get("observations")


def _absolute_trefle_url(url: str, base_url: str) -> str:
    if not url:
        return ""
    if urlparse(url).scheme:
        return url
    parsed_base = urlparse(base_url)
    root = f"{parsed_base.scheme}://{parsed_base.netloc}"
    return urljoin(root, url)


def _with_token(url: str, token: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("token", token)
    return urlunparse(parsed._replace(query=urlencode(query)))


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
