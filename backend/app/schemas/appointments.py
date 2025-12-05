from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AppointmentRecord(BaseModel):
    id: str
    timestamp: str
    caller_name: str
    company: str
    appointment: str
    category: str
    amount: str
    address: str
    summary: str
    raw_messages: str


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    text: str
    timestamp: str | None = None


class AppointmentCreateRequest(BaseModel):
    messages: list[ConversationMessage]
