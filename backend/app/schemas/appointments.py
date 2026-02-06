from __future__ import annotations

from typing import Literal, Any, Optional

from pydantic import BaseModel


AppointmentOperation = Literal["create", "update", "delete", "cancel"]


from datetime import datetime
from uuid import UUID

class AppointmentBase(BaseModel):
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


class AppointmentCreateRequest(AppointmentBase):
    pass
