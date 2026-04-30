"""Application service for completed-call appointment extraction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.model_defaults import resolve_generate_model
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import ExtractionRequest, ExtractionResponse
from app.services.appointments.extraction_applier import AppointmentExtractionApplier
from app.services.conversation import ConversationOrchestrator
from app.services.extraction_service import ExtractionService
from app.services.llm.factory import LLMFactory
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService


class AppointmentExtractionApplicationService:
    """Extract appointment data from a completed call and apply it to storage."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        call_repo: CallRepository,
        appointment_repo: AppointmentRepository,
        prompt_service: PromptService,
        extraction_applier: AppointmentExtractionApplier,
    ) -> None:
        self.db = db
        self.call_repo = call_repo
        self.appointment_repo = appointment_repo
        self.prompt_service = prompt_service
        self.extraction_applier = extraction_applier

    async def extract_appointment(self, request: ExtractionRequest) -> ExtractionResponse:
        try:
            call = await self.call_repo.get(request.call_id)
            if not call:
                raise ValueError("Call not found")

            existing = await self.appointment_repo.get_by_call_id(call.id)
            if existing:
                return ExtractionResponse(
                    success=True,
                    appointment_id=existing.id,
                    extracted_data=existing.extracted_data or {},
                    confidence=1.0,
                    message="已有预约记录，跳过重复提取",
                )

            extra_data = dict(call.extra_data or {})
            operation_execution_response = self._build_operation_execution_response(extra_data)
            if operation_execution_response is not None:
                return operation_execution_response

            messages = ConversationOrchestrator.normalize_messages(extra_data.get("messages"))
            if not messages:
                messages = ConversationOrchestrator.parse_messages_from_transcript(call.transcript)
                if messages:
                    extra_data["messages"] = messages
                    call.extra_data = dict(extra_data)
                    await self.db.commit()

            if not messages:
                raise ValueError("No conversation found in call")

            template_code = request.template_code or extra_data.get(
                "template_code",
                "general_appointment",
            )
            runtime = await resolve_prompt_runtime(
                self.prompt_service,
                template_code=template_code,
                default_code=template_code,
                model_capability="generate",
            )
            template = runtime.template
            if not template:
                raise ValueError(f"Template '{template_code}' not found")

            llm_provider = extra_data.get("llm_provider") or runtime.llm_provider or "gemini"
            llm_model = resolve_generate_model(
                extra_data.get("llm_model"),
                fallback_model=runtime.llm_model,
            )

            llm_service = LLMFactory.create(
                provider=llm_provider,
                api_key=settings.google_api_key,
                model=llm_model,
            )

            extraction_service = ExtractionService(llm_service)
            extraction_result = await extraction_service.extract_appointment(
                conversation=messages,
                template=template,
            )

            return await self.extraction_applier.apply(
                call=call,
                extraction_result=extraction_result,
                messages=messages,
                template=template,
                template_code=template_code,
                llm_provider=llm_provider,
                llm_model=llm_model,
                extra_data=dict(extra_data),
            )
        except Exception as exc:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={},
                confidence=0.0,
                message=f"提取失败: {str(exc)}",
            )

    @staticmethod
    def _build_operation_execution_response(
        extra_data: dict,
    ) -> ExtractionResponse | None:
        operation_execution = extra_data.get("operation_execution")
        if not isinstance(operation_execution, dict):
            return None

        op_type = str(operation_execution.get("operation") or "").lower()
        appt_id = operation_execution.get("appointment_id")
        if op_type not in {"update", "cancel"} or not appt_id:
            return None

        try:
            resolved_id = UUID(str(appt_id))
        except (TypeError, ValueError):
            return None

        return ExtractionResponse(
            success=True,
            appointment_id=resolved_id,
            extracted_data=operation_execution,
            confidence=1.0,
            message="检测到本次会话已完成预约变更/取消，跳过新建提取",
        )
