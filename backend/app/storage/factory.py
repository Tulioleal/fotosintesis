from app.core.settings import get_settings
from app.storage.base import ObjectStorage
from app.storage.local import LocalObjectStorage


def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    return LocalObjectStorage(bucket=settings.object_storage_bucket)
