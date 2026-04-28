"""Presentation helpers for deterministic appointment business replies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.services.appointments.parsers import JapaneseAppointmentParser


class AppointmentBriefPresenter:
    """Format appointment records for confirmation and operation events."""

    @staticmethod
    def format_value(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return "、".join(items) if items else "-"
        normalized = str(value).strip()
        return normalized if normalized else "-"

    @classmethod
    def resolve_category(cls, appointment: Any) -> str:
        direct = JapaneseAppointmentParser.first_non_empty(getattr(appointment, "category", None))
        if direct:
            return direct

        extracted_data = getattr(appointment, "extracted_data", None)
        if not isinstance(extracted_data, dict):
            return "-"

        category = JapaneseAppointmentParser.resolve_category(
            JapaneseAppointmentParser.first_non_empty(extracted_data.get("category")),
            extracted_data,
        )
        return cls.format_value(category)

    @classmethod
    def resolve_amount(cls, appointment: Any) -> str:
        direct = JapaneseAppointmentParser.first_non_empty(getattr(appointment, "amount", None))
        if direct:
            return direct

        extracted_data = getattr(appointment, "extracted_data", None)
        if not isinstance(extracted_data, dict):
            return "-"

        amount = JapaneseAppointmentParser.first_non_empty(extracted_data.get("amount"))
        if not amount and extracted_data.get("estimated_volume_m3") is not None:
            amount = f"{extracted_data.get('estimated_volume_m3')}m3"
        return cls.format_value(amount)

    @classmethod
    def format_appointment_brief(cls, appointment: Any, index: Optional[int] = None) -> str:
        prefix = f"[{index}] " if index is not None else ""
        appointment_time = (
            appointment.appointment.strftime("%Y-%m-%d %H:%M")
            if isinstance(appointment.appointment, datetime)
            else str(appointment.appointment)
        )
        company = cls.format_value(getattr(appointment, "company", None))
        category = cls.resolve_category(appointment)
        amount = cls.resolve_amount(appointment)
        address = cls.format_value(getattr(appointment, "address", None))
        extra_request = cls.format_value(getattr(appointment, "extra_request", None))
        return (
            f"{prefix}予約日時: {appointment_time} / "
            f"氏名: {appointment.caller_name} / "
            f"会社: {company} / "
            f"品目: {category} / "
            f"重量・容量: {amount} / "
            f"回収先住所: {address} / "
            f"備考: {extra_request}"
        )

