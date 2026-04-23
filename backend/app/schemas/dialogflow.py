from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DialogflowCreateAppointmentToolRequest(BaseModel):
    request_type: Literal["new"] = Field(
        description="固定为 new。仅用于新规预约落库。"
    )
    appointment_datetime: datetime = Field(
        description="ISO8601 with +09:00, e.g. 2026-04-29T12:00:00+09:00"
    )
    pickup_address: str = Field(min_length=1, description="回収先住所")
    waste_items: str = Field(min_length=1, description="回収対象の廃棄物の種類・品目")
    amount: Optional[str] = Field(default=None, description="量の目安")
    company_name: Optional[str] = Field(default=None, description="会社名。個人利用なら個人")
    contact_name: str = Field(min_length=1, description="担当者名")
    extra_request: Optional[str] = Field(default=None, description="追加要望。なければ特になし")
    user_confirmed: bool = Field(
        description="利用者が最終確認に明確に同意したか。true の場合のみ登録する。"
    )
    prompt_id: Optional[UUID] = Field(default=None, description="关联的本地 PromptTemplate UUID")
    prompt_code: Optional[str] = Field(
        default=None,
        description="关联的本地 PromptTemplate code。未提供时默认尝试使用 base_appointment。",
    )
    playbook_name: Optional[str] = Field(default=None, description="呼び出し元 playbook 名")
    session_id: Optional[str] = Field(default=None, description="Conversational Agents session id")
    call_sid: Optional[str] = Field(default=None, description="Twilio Call SID if available")

    @field_validator("pickup_address", "waste_items", "contact_name", mode="before")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("Required field cannot be empty.")
        return normalized

    @field_validator(
        "company_name",
        "amount",
        "extra_request",
        "prompt_code",
        "playbook_name",
        "session_id",
        "call_sid",
        mode="before",
    )
    @classmethod
    def _strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DialogflowCreateAppointmentToolResponse(BaseModel):
    appointment_id: UUID
    summary: str
    message: str = "予約を作成しました。"
