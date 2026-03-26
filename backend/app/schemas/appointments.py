from __future__ import annotations

from typing import Literal, Any, Optional

from pydantic import BaseModel, field_validator
from app.schemas.base import PaginatedResponse
from app.utils.datetime_utils import to_tokyo_aware


AppointmentOperation = Literal["create", "update", "delete", "cancel"]


from datetime import datetime
from uuid import UUID

class AppointmentBase(BaseModel):
    model_config = {"from_attributes": True}
    call_id: Optional[UUID] = None
    timestamp: datetime
    caller_name: str
    company: Optional[str] = None
    appointment: datetime
    category: Optional[str] = None
    amount: Optional[str] = None
    address: Optional[str] = None
    summary: str
    extra_request: Optional[str] = None
    raw_messages: Optional[Any] = None
    operation: Optional[AppointmentOperation] = "create"
    is_handled: bool = False
    extra_data: Optional[dict] = None
    
    # Dynamic Schema Extensions
    prompt_id: Optional[UUID] = None
    type_name: Optional[str] = None
    extracted_data: Optional[dict] = None

    @field_validator("operation", mode="before")
    @classmethod
    def coerce_operation(cls, v: Any) -> str:
        """将数据库中的 NULL operation 归一化为默认值 'create'"""
        return v if v in ("create", "update", "delete", "cancel") else "create"

    @field_validator("timestamp", "appointment")
    @classmethod
    def ensure_tokyo_datetime(cls, v: datetime) -> datetime:
        return to_tokyo_aware(v) or v

class AppointmentRecord(AppointmentBase):
    id: UUID

class AppointmentResponse(AppointmentRecord):
    pass

class AppointmentsResponse(PaginatedResponse[AppointmentResponse]):
    pass

class AppointmentCreateRequest(AppointmentBase):
    pass
