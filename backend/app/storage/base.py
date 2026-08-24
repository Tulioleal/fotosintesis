from abc import ABC, abstractmethod

from app.storage.models import ObjectContent, ObjectUpload, StoredObject


class ObjectStorageConfigurationError(ValueError):
    """Raised when the storage factory cannot build a provider from settings."""


class ObjectNotFoundError(LookupError):
    """Raised when a requested object does not exist in storage."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Object not found: {path}")
        self.path = path


class ObjectStorage(ABC):
    @abstractmethod
    async def put_object(self, upload: ObjectUpload) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    async def get_object(self, path: str) -> ObjectContent:
        raise NotImplementedError

    @abstractmethod
    async def delete_object(self, path: str) -> None:
        raise NotImplementedError
