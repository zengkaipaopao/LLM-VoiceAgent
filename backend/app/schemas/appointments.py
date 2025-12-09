from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


AppointmentOperation = Literal["create", "update", "delete"]


class AppointmentBase(BaseModel):
    timestamp: str
    caller_name: str
    company: str
    appointment: str
    category: str
    amount: str
    address: str
    summary: str
    extra_request: str = ""
    raw_messages: str
    operation: AppointmentOperation = "create"


class AppointmentRecord(AppointmentBase):
    id: str


class AppointmentCreateRequest(AppointmentBase):
    pass
