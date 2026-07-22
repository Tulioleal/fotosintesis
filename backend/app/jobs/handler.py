from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.jobs.schemas import (
    JobError,
    JobFailureCategory,
    JobStatus,
    JobType,
    ReadJobResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobHandlerResult:
    status: JobStatus
    result: ReadJobResult | None = None
    error: JobError | None = None
    retry_at: float | None = None

    @classmethod
    def failed(
        cls, *, category: JobFailureCategory, retryable: bool
    ) -> "JobHandlerResult":
        return cls(
            status=JobStatus.failed,
            error=JobError(category=category, retryable=retryable),
        )


class RetryableJobError(RuntimeError):
    def __init__(self, category: JobFailureCategory) -> None:
        self.category = category
        super().__init__(category.value)


class PermanentJobError(RuntimeError):
    def __init__(self, category: JobFailureCategory) -> None:
        self.category = category
        super().__init__(category.value)


class JobHandler(ABC):
    @abstractmethod
    async def handle(
        self, *, payload: BaseModel, attempt_count: int, max_attempts: int
    ) -> JobHandlerResult:
        ...

    def validate_dependencies(self) -> None:
        return None


@dataclass
class HandlerRegistryEntry:
    handler: JobHandler
    payload_models: dict[int, type[BaseModel]] = field(default_factory=dict)


@dataclass
class HandlerRegistry:
    _entries: dict[str, HandlerRegistryEntry] = field(default_factory=dict)

    def register(
        self,
        job_type: str,
        handler: JobHandler,
        *,
        payload_models: Mapping[int, type[BaseModel]],
    ) -> None:
        normalized_job_type = JobType(job_type).value
        normalized_models = dict(payload_models)

        if not normalized_models:
            raise ValueError(
                "at least one payload version must be registered"
            )

        for version, model in normalized_models.items():
            if type(version) is not int or version < 1:
                raise ValueError(
                    "payload versions must be positive integers"
                )
            if not isinstance(model, type) or not issubclass(
                model,
                BaseModel,
            ):
                raise TypeError(
                    "payload models must be Pydantic BaseModel classes"
                )

        existing = self._entries.get(normalized_job_type)
        if existing is not None:
            if (
                type(existing.handler) is type(handler)
                and existing.payload_models == normalized_models
            ):
                return
            raise ValueError(f"handler already registered for {normalized_job_type}")

        self._entries[normalized_job_type] = HandlerRegistryEntry(
            handler=handler,
            payload_models=normalized_models,
        )
        logger.info(
            "job_handler_registered",
            extra={
                "ctx_job_type": normalized_job_type,
                "ctx_payload_versions": sorted(normalized_models),
            },
        )

    def get_handler(self, job_type: str) -> JobHandler | None:
        entry = self._entries.get(job_type)
        return entry.handler if entry else None

    def get_payload_model(
        self,
        job_type: str,
        payload_version: int,
    ) -> type[BaseModel] | None:
        entry = self._entries.get(job_type)
        if entry is None:
            return None
        return entry.payload_models.get(payload_version)

    def has_handler(self, job_type: str) -> bool:
        return job_type in self._entries

    def validate_dependencies(self) -> None:
        for entry in self._entries.values():
            entry.handler.validate_dependencies()

    @property
    def registered_types(self) -> list[str]:
        return list(self._entries.keys())


_handler_registry: HandlerRegistry | None = None


def get_handler_registry() -> HandlerRegistry:
    global _handler_registry
    if _handler_registry is None:
        _handler_registry = HandlerRegistry()
    return _handler_registry
