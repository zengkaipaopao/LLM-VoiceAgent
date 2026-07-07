"""Authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class AuthenticatedUser(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str
    auth_provider: str


class AuthSessionResponse(BaseModel):
    user: AuthenticatedUser
    csrf_token: str
