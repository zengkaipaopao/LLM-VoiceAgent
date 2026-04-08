"""
Bridge finalized test sessions to extraction or existing appointment records.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional
from uuid import UUID

from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.chat import ExtractionRequest, ExtractionResponse

ExtractAppointmentRunner = Callable[[ExtractionRequest], Awaitable[ExtractionResponse]]


class ExtractionBridgeService:
    """Resolve how a finalized test session should map to an appointment result."""

    __test__ = False

    def __init__(
        self,
        *,
        appointment_repo: AppointmentRepository,
        extract_appointment: ExtractAppointmentRunner | None = None,
    ) -> None:
        self.appointment_repo = appointment_repo
        self.extract_appointment = extract_appointment

    async def resolve_finalized_call(
        self,
        *,
        call: Call,
        template_code: Optional[str] = None,
    ) -> tuple[Optional[UUID], Optional[ExtractionResponse], bool]:
        extra_data = call.extra_data or {}
        operation_execution = extra_data.get("operation_execution")
        if isinstance(operation_execution, dict):
            op_type = str(operation_execution.get("operation") or "").lower()
            appt_id = operation_execution.get("appointment_id")
            if op_type in {"update", "cancel"} and appt_id:
                try:
                    appointment_id = UUID(str(appt_id))
                except (TypeError, ValueError):
                    appointment_id = None
                if appointment_id:
                    extraction_result = ExtractionResponse(
                        success=True,
                        appointment_id=appointment_id,
                        extracted_data=operation_execution,
                        confidence=1.0,
                        message="已执行预约变更/取消，跳过新建提取",
                    )
                    return appointment_id, extraction_result, True

        existing = await self.appointment_repo.get_by_call_id(call.id)
        if existing:
            extraction_result = ExtractionResponse(
                success=True,
                appointment_id=existing.id,
                extracted_data=existing.extracted_data or {},
                confidence=1.0,
                message="已有预约记录，跳过重复提取",
            )
            return existing.id, extraction_result, True

        if not self.extract_appointment:
            raise RuntimeError("extract_appointment callback is required when run_extraction=True")

        extraction_result = await self.extract_appointment(
            ExtractionRequest(
                call_id=call.id,
                template_code=template_code or extra_data.get("template_code"),
            )
        )
        return extraction_result.appointment_id, extraction_result, False
