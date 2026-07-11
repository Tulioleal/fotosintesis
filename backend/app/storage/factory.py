from functools import lru_cache

from app.core.settings import Settings, get_settings
from app.storage.base import ObjectStorage, ObjectStorageConfigurationError
from app.storage.local import LocalObjectStorage


def build_object_storage(settings: Settings | None = None) -> ObjectStorage:
    settings = settings or get_settings()
    provider = (settings.object_storage_provider or "local").lower()
    if provider == "local":
        return LocalObjectStorage(
            bucket=settings.object_storage_bucket,
            root=settings.object_storage_local_root,
        )
    if provider == "gcs":
        from app.storage.gcs import GCSObjectStorage

        return GCSObjectStorage(
            bucket=settings.object_storage_bucket,
            project_id=settings.gcp_project_id or None,
        )
    raise ObjectStorageConfigurationError(
        f"Unknown OBJECT_STORAGE_PROVIDER: {settings.object_storage_provider!r}. "
        "Expected one of: local, gcs."
    )


@lru_cache
def get_object_storage() -> ObjectStorage:
    return build_object_storage()
