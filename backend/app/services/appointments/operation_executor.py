"""Executor for deterministic appointment update/cancel operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.services.appointments.parsers import JapaneseAppointmentParser
from app.services.appointments.presenter import AppointmentBriefPresenter
from app.services.transcript_sanitizer import sanitize_assistant_turn
from app.utils.datetime_utils import now_tokyo_naive


class AppointmentOperationExecutor:
    """Apply confirmed appointment operations and create operation event rows."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        appointment_repo: AppointmentRepository,
        flow_key: str = "appointment_operation_flow",
    ) -> None:
        self.db = db
        self.appointment_repo = appointment_repo
        self.flow_key = flow_key

    @staticmethod
    def _normalize_messages(raw_messages: Any) -> list[dict[str, str]]:
        if not isinstance(raw_messages, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            if role not in {"user", "assistant", "system"}:
                continue
            content = str(item.get("content", "")).strip()
            if role == "assistant":
                content = sanitize_assistant_turn(content).strip()
            if content:
                normalized.append({"role": role, "content": content})
        return normalized

    @classmethod
    def build_conversation_snapshot(
        cls,
        call: Call,
        *,
        user_message: str,
        assistant_message: str,
    ) -> list[dict[str, str]]:
        messages = cls._normalize_messages((call.extra_data or {}).get("messages"))
        user_text = user_message.strip()
        assistant_text = sanitize_assistant_turn(assistant_message)

        if user_text:
            messages.append({"role": "user", "content": user_text})
        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})
        return messages

    @staticmethod
    def build_event_summary(
        *,
        operation: str,
        target: Appointment,
        pending_changes: dict[str, str],
        target_brief: str,
    ) -> str:
        if operation == "cancel":
            return f"既存予約をキャンセル。対象: {target_brief}"

        changed_parts: list[str] = []
        if "appointment" in pending_changes:
            changed_parts.append("日時")
        if "address" in pending_changes:
            changed_parts.append("住所")
        if "amount" in pending_changes:
            changed_parts.append("数量")
        if "category" in pending_changes:
            changed_parts.append("カテゴリ")

        changed_text = "・".join(changed_parts) if changed_parts else "項目不明"
        caller_name = target.caller_name or "不明"
        return f"{caller_name}様の既存予約を変更。変更項目: {changed_text}"

    async def execute(
        self,
        *,
        call: Call,
        appointment: Appointment,
        operation: str,
        pending_changes: dict[str, str],
        flow: dict[str, Any],
        extra_data: dict[str, Any],
        user_message: str,
    ) -> str:
        now_dt = now_tokyo_naive()
        now_iso = now_dt.isoformat()
        appointment_extra_data = dict(appointment.extra_data or {})

        before_snapshot = {
            "appointment": (
                appointment.appointment.isoformat()
                if isinstance(appointment.appointment, datetime)
                else None
            ),
            "address": appointment.address,
            "amount": appointment.amount,
            "category": appointment.category,
            "lifecycle_status": appointment_extra_data.get("lifecycle_status", "active"),
        }

        if operation == "cancel":
            appointment_extra_data["lifecycle_status"] = "cancelled"
        else:
            if "appointment" in pending_changes:
                appointment.appointment = JapaneseAppointmentParser.parse_appointment_time(
                    pending_changes["appointment"]
                )
            if "address" in pending_changes:
                appointment.address = pending_changes["address"]
            if "amount" in pending_changes:
                appointment.amount = pending_changes["amount"]
            if "category" in pending_changes:
                appointment.category = pending_changes["category"]
            appointment_extra_data["lifecycle_status"] = "active"

        appointment_extra_data["last_operation_flow"] = {
            "operation": operation,
            "confirmed_at": now_iso,
            "changes": pending_changes,
            "note": flow.get("pending_note"),
            "call_id": str(call.id),
        }
        appointment_extra_data["latest_operation_type"] = operation
        appointment_extra_data["latest_operation_at"] = now_iso
        appointment_extra_data["latest_operation_call_id"] = str(call.id)
        appointment.extra_data = appointment_extra_data

        result_summary = AppointmentBriefPresenter.format_appointment_brief(appointment)
        done_label = (
            "キャンセルが完了しました。"
            if operation == "cancel"
            else "変更が完了しました。"
        )
        done_message = f"{done_label}\n{result_summary}"

        after_snapshot = {
            "appointment": (
                appointment.appointment.isoformat()
                if isinstance(appointment.appointment, datetime)
                else None
            ),
            "address": appointment.address,
            "amount": appointment.amount,
            "category": appointment.category,
            "lifecycle_status": appointment_extra_data.get("lifecycle_status", "active"),
        }
        conversation_snapshot = self.build_conversation_snapshot(
            call,
            user_message=user_message,
            assistant_message=done_message,
        )

        operation_event_data = {
            "call_id": call.id,
            "timestamp": now_dt,
            "caller_name": appointment.caller_name or call.caller_name or "Unknown",
            "company": appointment.company,
            "appointment": appointment.appointment or now_dt,
            "category": appointment.category,
            "amount": appointment.amount,
            "address": appointment.address,
            "summary": self.build_event_summary(
                operation=operation,
                target=appointment,
                pending_changes=pending_changes,
                target_brief=result_summary,
            ),
            "extra_request": appointment.extra_request,
            "operation": operation,
            "prompt_id": appointment.prompt_id,
            "type_name": appointment.type_name,
            "extracted_data": {
                "operation": operation,
                "target_appointment_id": str(appointment.id),
                "changes": pending_changes,
                "before": before_snapshot,
                "after": after_snapshot,
                "confirmed_at": now_iso,
            },
            "extra_data": {
                "simulation": bool(extra_data.get("simulation", False)),
                "source": extra_data.get("source", "chat"),
                "template_code": extra_data.get("template_code"),
                "llm_provider": extra_data.get("llm_provider"),
                "llm_model": extra_data.get("llm_model"),
                "target_appointment_id": str(appointment.id),
                "target_call_id": str(appointment.call_id) if appointment.call_id else None,
                "operation_flow": {
                    "operation": operation,
                    "confirmed_at": now_iso,
                },
            },
            "raw_messages": {
                "extraction_source": "operation_flow",
                "conversation": conversation_snapshot,
                "operation": operation,
                "target_appointment_id": str(appointment.id),
            },
        }

        operation_event = await self.appointment_repo.create(operation_event_data)
        appointment_extra_data["latest_operation_event_id"] = str(operation_event.id)
        appointment.extra_data = appointment_extra_data
        await self.db.commit()

        extra_data["operation_execution"] = {
            "operation": operation,
            "appointment_id": str(operation_event.id),
            "target_appointment_id": str(appointment.id),
            "confirmed_at": now_iso,
        }
        extra_data.pop(self.flow_key, None)
        call.extra_data = extra_data

        return done_message
