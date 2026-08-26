from datetime import datetime, timezone
from pathlib import Path

from app.storage.base import ObjectNotFoundError, ObjectStorage
from app.storage.models import ObjectContent, ObjectUpload, StoredObject


class LocalObjectStorage(ObjectStorage):
    def __init__(self, bucket: str, root: Path | str = "/tmp/storage-data") -> None:
        self.bucket = bucket
        self.root = Path(root)

    def _target(self, path: str) -> Path:
        return self.root / self.bucket / path

    async def put_object(self, upload: ObjectUpload) -> StoredObject:
        target = self._target(upload.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(upload.content)

        return StoredObject(
            bucket=self.bucket,
            path=upload.path,
            mime_type=upload.mime_type,
            size_bytes=len(upload.content),
            created_at=datetime.now(timezone.utc),
            expires_at=upload.expires_at,
        )

    async def get_object(self, path: str) -> ObjectContent:
        target = self._target(path)
        if not target.is_file():
            raise ObjectNotFoundError(path)
        content = target.read_bytes()
        mime_type = self._guessed_mime_type(target)
        return ObjectContent(content=content, mime_type=mime_type, size_bytes=len(content))

    async def delete_object(self, path: str) -> None:
        target = self._target(path)
        if target.exists():
            target.unlink()

    @staticmethod
    def _guessed_mime_type(target: Path) -> str:
        import mimetypes

        guessed, _ = mimetypes.guess_type(target.name)
        return guessed or "application/octet-stream"
