from abc import ABC, abstractmethod

from app.storage.models import ObjectUpload, StoredObject


class ObjectStorageConfigurationError(ValueError):
    """Raised when the storage factory cannot build a provider from settings."""


class ObjectStorage(ABC):
    @abstractmethod
    async def put_object(self, upload: ObjectUpload) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    async def delete_object(self, path: str) -> None:
        raise NotImplementedError
