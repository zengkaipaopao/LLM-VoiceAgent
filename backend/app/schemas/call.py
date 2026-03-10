"""
Call schemas for request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from enum import Enum
from app.schemas.base import PaginatedResponse


class CallDirection(str, Enum):
    """Call direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Call status."""
    RINGING = "ringing"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"


class HandlerType(str, Enum):
    """Handler type."""
    AI = "ai"
    HUMAN = "human"
    TRANSFERRED = "transferred"


class CallBase(BaseModel):
    """Base call schema."""
    direction: CallDirection
    counterpart: str = Field(..., min_length=1, max_length=50, description="Phone number")


class CallCreate(CallBase):
    """Schema for creating a call."""
    prompt_id: Optional[UUID] = None
    started_at: Optional[datetime] = None


class CallUpdate(BaseModel):
    """Schema for updating a call."""
    status: Optional[CallStatus] = None
    summary: Optional[str] = None
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, ge=0)


class CallResponse(CallBase):
    """Schema for call response."""
    id: UUID
    caller_name: Optional[str] = None
    started_at: datetime
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: int
    status: CallStatus
    handler_type: Optional[HandlerType] = None
    is_answered: bool = False
    summary: Optional[str] = None
    transcript: Optional[str] = None
    ai_confidence: Optional[int] = None
    transferred_at: Optional[datetime] = None
    transfer_reason: Optional[str] = None
    sip_call_id: Optional[str] = None
    sip_from: Optional[str] = None
    sip_to: Optional[str] = None
    prompt_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    extra_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

    @field_validator("started_at", "answered_at", "ended_at", "transferred_at", "created_at", "updated_at")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class CallListResponse(PaginatedResponse[CallResponse]):
    """Schema for paginated call list."""
    pass
