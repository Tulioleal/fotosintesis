from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    path: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ObjectUpload:
    path: str
    content: bytes
    mime_type: str
    expires_at: datetime | None = None
