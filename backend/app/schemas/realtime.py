from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RealtimeSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model: str | None = Field(default=None, alias="model_id")
    voice: str | None = None
    instructions: str | None = None
    sip: dict[str, Any] | None = None


class RealtimeClientSecret(BaseModel):
    value: str
    expires_at: int | None = None


class RealtimeSessionResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id: str
    model: str
    expires_at: int | None = None
    client_secret: RealtimeClientSecret
    websocket_url: str | None = None
    rtc_configuration: dict[str, Any] | None = None


class RealtimeSessionDTO(BaseModel):
    """Simplified response returned to the frontend."""

    session_id: str
    model: str
    expires_at: int | None = None
    client_secret: str
    websocket_url: str | None = None
    rtc_configuration: dict[str, Any] | None = None
