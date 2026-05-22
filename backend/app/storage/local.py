from datetime import UTC, datetime
from pathlib import Path

from app.storage.base import ObjectStorage
from app.storage.models import ObjectUpload, StoredObject


class LocalObjectStorage(ObjectStorage):
    def __init__(self, bucket: str, root: Path | str = "storage-data") -> None:
        self.bucket = bucket
        self.root = Path(root)

    async def put_object(self, upload: ObjectUpload) -> StoredObject:
        target = self.root / self.bucket / upload.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(upload.content)

        return StoredObject(
            bucket=self.bucket,
            path=upload.path,
            mime_type=upload.mime_type,
            size_bytes=len(upload.content),
            created_at=datetime.now(UTC),
            expires_at=upload.expires_at,
        )

    async def delete_object(self, path: str) -> None:
        target = self.root / self.bucket / path
        if target.exists():
            target.unlink()
