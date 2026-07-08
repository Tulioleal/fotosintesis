from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.storage.base import ObjectStorage
from app.storage.models import ObjectUpload, StoredObject


class GCSObjectStorage(ObjectStorage):
    """GCS-backed object storage using Workload Identity / Application Default Credentials.

    The Google Cloud Python client uses Application Default Credentials, so the
    backend runtime service account's Workload Identity binding is enough to
    authorize `storage.objects.create` / `storage.objects.get` / `storage.objects.delete`
    on the configured bucket. No static access keys are required.
    """

    def __init__(self, bucket: str, project_id: str | None = None) -> None:
        if not bucket:
            raise ValueError("GCSObjectStorage requires a non-empty bucket name.")
        self.bucket = bucket
        self.project_id = project_id
        self._client: Any | None = None
        self._bucket: Any | None = None
        self._lock = asyncio.Lock()

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - import guard
                raise RuntimeError(
                    "google-cloud-storage is required for OBJECT_STORAGE_PROVIDER=gcs. "
                    "Install it in the backend image or switch the provider to 'local'."
                ) from exc
            self._client = storage.Client(project=self.project_id) if self.project_id else storage.Client()
            self._bucket = self._client.bucket(self.bucket)
        return self._client

    def _ensure_bucket(self) -> Any:
        self._ensure_client()
        assert self._bucket is not None
        return self._bucket

    async def put_object(self, upload: ObjectUpload) -> StoredObject:
        def _upload() -> None:
            bucket = self._ensure_bucket()
            blob = bucket.blob(upload.path)
            blob.upload_from_string(
                data=upload.content,
                content_type=upload.mime_type,
            )

        await asyncio.to_thread(_upload)
        return StoredObject(
            bucket=self.bucket,
            path=upload.path,
            mime_type=upload.mime_type,
            size_bytes=len(upload.content),
            created_at=datetime.now(timezone.utc),
            expires_at=upload.expires_at,
        )

    async def delete_object(self, path: str) -> None:
        def _delete() -> None:
            bucket = self._ensure_bucket()
            blob = bucket.blob(path)
            if blob.exists():
                blob.delete()

        await asyncio.to_thread(_delete)
