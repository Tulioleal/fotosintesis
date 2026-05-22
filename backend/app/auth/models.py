from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AuthUser:
    id: UUID
    name: str
    email: str
    password_hash: str
    email_verified: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class AuthSession:
    id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    absolute_expires_at: datetime
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None = None


@dataclass
class RecoveryToken:
    id: UUID
    user_id: UUID | None
    token: str
    expires_at: datetime
    created_at: datetime
