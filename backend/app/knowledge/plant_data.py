from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.knowledge.schemas import KnowledgeDocumentInput, KnowledgeSourceInput, ReviewStatus
from app.providers.interfaces import PlantDataProvider
from app.providers.types import PlantDataResult

CARE_FIELDS = {"watering", "sunlight", "soil", "maintenance", "pests", "care"}
BOTANICAL_FIELDS = {"description", "family", "genus", "rank", "common_name"}


class StructuredPlantEvidence(BaseModel):
    scientific_name: str
    topic: str
    content: str
    confidence: float = Field(ge=0, le=1)
    sources: list[KnowledgeSourceInput]
    providers: list[str]
    fields: dict[str, object] = Field(default_factory=dict)
    sufficient: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    def to_document(self) -> KnowledgeDocumentInput:
        return KnowledgeDocumentInput(
            scientific_name=self.scientific_name,
            topic=self.topic,
            title=f"{self.scientific_name}: {self.topic} structured plant data",
            content=self.content,
            confidence=self.confidence,
            review_status=ReviewStatus.auto_ingested,
            sources=self.sources,
        )


class PlantDataLookupService:
    def __init__(self, *, trefle: PlantDataProvider, perenual: PlantDataProvider) -> None:
        self.trefle = trefle
        self.perenual = perenual

    async def lookup(self, *, scientific_name: str, topic: str) -> StructuredPlantEvidence | None:
        scientific_name = scientific_name.strip()
        if not _looks_like_scientific_name(scientific_name):
            return None

        trefle_result = await self.trefle.lookup(scientific_name)
        if trefle_result and _sufficient(trefle_result.fields, topic):
            return _normalize(scientific_name=scientific_name, topic=topic, results=[trefle_result])

        results = [trefle_result] if trefle_result else []
        if _care_topic(topic):
            perenual_result = await self.perenual.lookup(scientific_name)
            if perenual_result:
                results.append(perenual_result)
        if not results:
            return None
        evidence = _normalize(scientific_name=scientific_name, topic=topic, results=results)
        return evidence if evidence.content.strip() else None


def _normalize(
    *, scientific_name: str, topic: str, results: list[PlantDataResult]
) -> StructuredPlantEvidence:
    now = datetime.now(timezone.utc)
    merged: dict[str, object] = {}
    providers: list[str] = []
    sources: list[KnowledgeSourceInput] = []
    for result in results:
        providers.append(result.provider)
        for key, value in result.fields.items():
            if _present(value) and key not in merged:
                merged[key] = value
        sources.append(
            KnowledgeSourceInput(
                title=f"{result.provider} structured plant data",
                url=result.source_url,
                source_domain=_domain(result.source_url),
                retrieved_at=now,
                validation_status="structured_api",
            )
        )
    missing = _missing_fields(merged, topic)
    sufficient = not missing
    return StructuredPlantEvidence(
        scientific_name=scientific_name,
        topic=topic,
        content=_content(scientific_name, topic, merged, providers),
        confidence=0.72 if sufficient else 0.45,
        sources=sources,
        providers=providers,
        fields=merged,
        sufficient=sufficient,
        missing_fields=missing,
    )


def _sufficient(fields: dict[str, Any], topic: str) -> bool:
    return not _missing_fields(fields, topic)


def _missing_fields(fields: dict[str, Any], topic: str) -> list[str]:
    if _care_topic(topic):
        required = {_topic_field(topic)} if _topic_field(topic) else CARE_FIELDS
    else:
        required = BOTANICAL_FIELDS
    return sorted(field for field in required if not _present(fields.get(field)))


def _topic_field(topic: str) -> str | None:
    normalized = topic.casefold().strip()
    if normalized in CARE_FIELDS:
        return normalized
    if normalized in {"light", "sun", "shade"}:
        return "sunlight"
    if normalized in {"pest", "plague"}:
        return "pests"
    return None


def _care_topic(topic: str) -> bool:
    normalized = topic.casefold().strip()
    return normalized in CARE_FIELDS or normalized in {"care", "light", "sun", "shade", "pest", "plague"}


def _content(
    scientific_name: str, topic: str, fields: dict[str, object], providers: list[str]
) -> str:
    evidence = "; ".join(
        f"{_label(key)}: {_string_value(value)}"
        for key, value in fields.items()
        if _present(value)
    )
    return (
        f"Structured plant data for {scientific_name} about {topic}. {evidence}. "
        f"Providers: {', '.join(providers)}."
    )


def _looks_like_scientific_name(value: str) -> bool:
    parts = [part for part in value.split() if part]
    return len(parts) >= 2 and all(part.replace("-", "").isalpha() for part in parts[:2])


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return bool(value)
    return True


def _string_value(value: object) -> str:
    if isinstance(value, list | tuple | set):
        return ", ".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return ", ".join(f"{key}: {val}" for key, val in value.items() if str(val).strip())
    return str(value)


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower() or url
