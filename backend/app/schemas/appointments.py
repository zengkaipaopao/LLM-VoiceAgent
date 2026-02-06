from __future__ import annotations

from typing import Literal, Any, Optional

from pydantic import BaseModel


AppointmentOperation = Literal["create", "update", "delete", "cancel"]


from datetime import datetime
from uuid import UUID

class AppointmentBase(BaseModel):
    model_config = {"from_attributes": True}
    timestamp: datetime
    caller_name: str
    company: str
    appointment: datetime
    category: str
    amount: str
    address: str
    summary: str
    extra_request: str = ""
    raw_messages: Optional[Any] = None
    operation: AppointmentOperation = "create"
    is_handled: bool = False
    extra_data: Optional[dict] = None  # Add this

class AppointmentRecord(AppointmentBase):
    id: UUID

class AppointmentResponse(AppointmentRecord):
    pass

class AppointmentsResponse(BaseModel):
    items: list[AppointmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class AppointmentCreateRequest(AppointmentBase):
    pass
