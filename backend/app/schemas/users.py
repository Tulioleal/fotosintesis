from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from app.schemas.common import ApiSchema


class UserDto(ApiSchema):
    id: UUID
    email: EmailStr
    name: str
    region: str | None = None
    created_at: datetime
