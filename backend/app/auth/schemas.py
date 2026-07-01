from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class PublicAuthUser(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    email_verified: bool


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RegisterResponse(BaseModel):
    user: PublicAuthUser


class CredentialsVerifyRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class CredentialsVerifyResponse(BaseModel):
    user: PublicAuthUser
    session_token: str
    session_expires_at: datetime


class RecoveryRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RecoveryResponse(BaseModel):
    status: str
    message: str


class RecoveryConfirmRequest(BaseModel):
    token: str = Field(min_length=16)
    password: str = Field(min_length=8)


class HomeAccessItem(BaseModel):
    key: str
    label: str
    href: str
    status: str = "placeholder"


class GardenPlantCard(BaseModel):
    id: UUID
    scientific_name: str
    common_name: str | None = None
    nickname: str | None = None
    image_path: str | None = None
    location: str | None = None
    active_reminders: int = 0
    created_at: datetime


class HomeSummaryResponse(BaseModel):
    user: PublicAuthUser
    empty_state: bool
    access: list[HomeAccessItem]
    garden_count: int = 0
    recent_garden_plants: list[GardenPlantCard] = Field(default_factory=list)
