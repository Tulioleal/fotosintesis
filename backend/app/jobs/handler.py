from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.jobs.schemas import JobError, JobFailureCategory, JobStatus, ReadJobResult

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

    @abstractmethod
    def supported_payload_versions(self) -> list[int]:
        ...

    def payload_model(self, payload_version: int) -> type[BaseModel] | None:
        return None

    def validate_dependencies(self) -> None:
        return None


@dataclass
class HandlerRegistryEntry:
    handler: JobHandler
    payload_model: type[BaseModel] | None = None


@dataclass
class HandlerRegistry:
    _entries: dict[str, HandlerRegistryEntry] = field(default_factory=dict)

    def register(
        self,
        job_type: str,
        handler: JobHandler,
        *,
        payload_model: type[BaseModel] | None = None,
    ) -> None:
        self._entries[job_type] = HandlerRegistryEntry(
            handler=handler, payload_model=payload_model
        )
        logger.info(
            "job_handler_registered",
            extra={
                "ctx_job_type": job_type,
                "ctx_payload_versions": handler.supported_payload_versions(),
            },
        )

    def get_handler(self, job_type: str) -> JobHandler | None:
        entry = self._entries.get(job_type)
        return entry.handler if entry else None

    def get_payload_model(self, job_type: str) -> type[BaseModel] | None:
        entry = self._entries.get(job_type)
        return entry.payload_model if entry else None

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
