"""Apply LLM appointment extraction results to appointment records."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.chat import ExtractionResponse
from app.services.appointments.operation_executor import AppointmentOperationExecutor
from app.services.appointments.operation_matcher import AppointmentOperationMatcher
from app.services.appointments.parsers import JapaneseAppointmentParser
from app.services.extraction_service import AppointmentExtraction
from app.utils.datetime_utils import now_tokyo_naive


class AppointmentExtractionApplier:
    """Persist create/update/cancel outcomes from an LLM extraction result."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        appointment_repo: AppointmentRepository,
        matcher: AppointmentOperationMatcher,
        executor: AppointmentOperationExecutor,
    ) -> None:
        self.db = db
        self.appointment_repo = appointment_repo
        self.matcher = matcher
        self.executor = executor

    async def apply(
        self,
        *,
        call: Call,
        extraction_result: AppointmentExtraction,
        messages: list[dict[str, str]],
        template: Any,
        template_code: str,
        llm_provider: str,
        llm_model: str,
        extra_data: dict[str, Any],
    ) -> ExtractionResponse:
        raw_data = extraction_result.raw_data or {}
        operation_resolution = await self.try_apply_operation_request(
            call=call,
            raw_data=raw_data,
            extraction_summary=extraction_result.summary
            or extraction_result.appointment_content,
            extraction_confidence=extraction_result.confidence,
            extra_data=dict(extra_data),
        )
        if operation_resolution is not None:
            return operation_resolution

        appointment = await self.appointment_repo.create(
            self._build_create_payload(
                call=call,
                extraction_result=extraction_result,
                raw_data=raw_data,
                messages=messages,
                template=template,
                template_code=template_code,
                llm_provider=llm_provider,
                llm_model=llm_model,
                extra_data=extra_data,
            )
        )

        return ExtractionResponse(
            success=True,
            appointment_id=appointment.id,
            extracted_data=extraction_result.model_dump(),
            confidence=extraction_result.confidence,
            message="预约信息提取成功",
        )

    async def try_apply_operation_request(
        self,
        *,
        call: Call,
        raw_data: dict[str, Any],
        extraction_summary: str,
        extraction_confidence: float,
        extra_data: dict[str, Any],
    ) -> ExtractionResponse | None:
        operation = JapaneseAppointmentParser.extract_operation_type_from_raw_data(raw_data)
        if operation not in {"cancel", "update"}:
            return None

        target = await self.matcher.resolve_extracted_operation_target(
            call=call,
            raw_data=raw_data,
        )
        if not target:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={
                    "operation": operation,
                    "resolution_status": "target_not_found",
                    "extracted_data": raw_data,
                },
                confidence=extraction_confidence,
                message="检测到预约变更/取消请求，但未能匹配目标预约，已跳过新预约创建",
            )

        pending_changes = (
            JapaneseAppointmentParser.build_update_changes_from_extraction(raw_data)
            if operation == "update"
            else {}
        )
        if operation == "update" and not pending_changes:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={
                    "operation": operation,
                    "target_appointment_id": str(target.id),
                    "resolution_status": "missing_update_changes",
                    "extracted_data": raw_data,
                },
                confidence=extraction_confidence,
                message="检测到预约变更请求并找到目标预约，但未抽取到变更内容，已跳过新预约创建",
            )

        await self.executor.execute(
            call=call,
            appointment=target,
            operation=operation,
            pending_changes=pending_changes,
            flow={"operation": operation, "pending_note": extraction_summary},
            extra_data=dict(extra_data),
            user_message=extraction_summary,
        )
        await self.db.commit()

        operation_execution = dict(call.extra_data or {}).get("operation_execution")
        operation_event_id = self._parse_operation_event_id(operation_execution)

        return ExtractionResponse(
            success=True,
            appointment_id=operation_event_id,
            extracted_data={
                "operation": operation,
                "target_appointment_id": str(target.id),
                "operation_event_id": (
                    str(operation_event_id) if operation_event_id else None
                ),
                "changes": pending_changes,
                "resolution_status": "executed_from_llm_extraction",
                "extracted_data": raw_data,
            },
            confidence=extraction_confidence,
            message="检测到预约变更/取消请求，已更新目标预约并创建操作事件",
        )

    def _build_create_payload(
        self,
        *,
        call: Call,
        extraction_result: AppointmentExtraction,
        raw_data: dict[str, Any],
        messages: list[dict[str, str]],
        template: Any,
        template_code: str,
        llm_provider: str,
        llm_model: str,
        extra_data: dict[str, Any],
    ) -> dict[str, Any]:
        conversation_text = "\n".join(
            str(message.get("content", "")).strip()
            for message in messages
            if isinstance(message, dict)
            and str(message.get("content", "")).strip()
        )
        resolved_amount = JapaneseAppointmentParser.resolve_amount(
            raw_data,
            extraction_result.summary,
            extraction_result.appointment_content,
            getattr(call, "transcript", None),
            conversation_text,
        )
        return {
            "call_id": call.id,
            "timestamp": now_tokyo_naive(),
            "caller_name": extraction_result.caller_name
            or call.caller_name
            or "Unknown",
            "company": extraction_result.company,
            "appointment": JapaneseAppointmentParser.parse_appointment_time(
                extraction_result.appointment_time
            ),
            "category": JapaneseAppointmentParser.resolve_category(
                extraction_result.category,
                raw_data,
            ),
            "amount": resolved_amount,
            "address": JapaneseAppointmentParser.resolve_address(raw_data),
            "summary": extraction_result.summary
            or extraction_result.appointment_content
            or "提取的预约信息",
            "extra_request": JapaneseAppointmentParser.resolve_extra_request(raw_data),
            "operation": "create",
            "prompt_id": template.id if template else None,
            "type_name": template.category if template else "general",
            "extracted_data": raw_data,
            "extra_data": {
                "simulation": bool(extra_data.get("simulation", False)),
                "source": extra_data.get("source", "chat"),
                "simulated_phone": extra_data.get("simulated_phone"),
                "llm_provider": llm_provider,
                "llm_model": llm_model,
            },
            "raw_messages": {
                "extraction_source": "llm_chat",
                "template_code": template_code,
                "confidence": extraction_result.confidence,
                "conversation": messages,
                "extracted_data": raw_data,
            },
        }

    @staticmethod
    def _parse_operation_event_id(operation_execution: Any) -> UUID | None:
        if not isinstance(operation_execution, dict):
            return None
        try:
            return UUID(str(operation_execution.get("appointment_id")))
        except (TypeError, ValueError):
            return None
