from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=14, max_length=1024)


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential
    expires_at: datetime


class ResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    title: str
    version: int


class JobCreate(BaseModel):
    kind: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    idempotency_key: str = Field(min_length=8, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    kind: str
    state: str
    idempotency_key: str
    attempt_count: int
    version: int


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    sha256: str
    size_bytes: int
    media_type: str
    original_name: str
    scanner_status: str


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)
