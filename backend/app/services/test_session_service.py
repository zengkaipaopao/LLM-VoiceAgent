"""
Test session lifecycle service for the test lab flows.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.model_defaults import require_generate_model
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ExtractionResponse,
    TestSessionFinalizeResponse,
    TestSessionStartResponse,
)
from app.services.extraction_bridge import ExtractAppointmentRunner, ExtractionBridgeService
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.utils.datetime_utils import now_tokyo_naive


class TestSessionService:
    """Manage test session creation/finalization separate from chat runtime logic."""
    __test__ = False

    def __init__(
        self,
        db: AsyncSession,
        *,
        call_repo: CallRepository | None = None,
        appointment_repo: AppointmentRepository | None = None,
        prompt_service: PromptService | None = None,
        extract_appointment: ExtractAppointmentRunner | None = None,
        extraction_bridge: ExtractionBridgeService | None = None,
    ) -> None:
        self.db = db
        self.call_repo = call_repo or CallRepository(db)
        self.appointment_repo = appointment_repo or AppointmentRepository(db)
        self.prompt_service = prompt_service or PromptService(db)
        self.extract_appointment = extract_appointment
        self.extraction_bridge = extraction_bridge or ExtractionBridgeService(
            appointment_repo=self.appointment_repo,
            extract_appointment=self.extract_appointment,
        )

    @staticmethod
    def _generate_simulated_phone() -> str:
        prefix = random.choice(["70", "80", "90"])
        subscriber = "".join(str(random.randint(0, 9)) for _ in range(8))
        return f"+81{prefix}{subscriber}"

    @staticmethod
    def _compute_duration_seconds(started_at: Optional[datetime], ended_at: Optional[datetime]) -> int:
        if not started_at or not ended_at:
            return 0
        return max(0, int((ended_at - started_at).total_seconds()))

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> TestSessionStartResponse:
        runtime = await resolve_prompt_runtime(
            self.prompt_service,
            template_code=template_code,
            default_code=template_code,
            model_capability="generate",
        )
        template = runtime.template
        if not template:
            raise ValueError(f"Template '{template_code}' not found")

        llm_provider = provider or runtime.llm_provider or "gemini"
        llm_model = require_generate_model(
            model or runtime.llm_model,
            source="Prompt llm_model",
        )
        started_at = now_tokyo_naive()
        simulated_phone = self._generate_simulated_phone()

        call = await self.call_repo.create(
            {
                "direction": "inbound",
                "counterpart": simulated_phone,
                "caller_name": caller_name or "Test Caller",
                "status": "ongoing",
                "handler_type": "ai",
                "is_answered": True,
                "started_at": started_at,
                "answered_at": started_at,
                "prompt_id": template.id,
                "extra_data": {
                    "simulation": True,
                    "source": "test_lab",
                    "simulated_phone": simulated_phone,
                    "template_code": runtime.template_code,
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "messages": [],
                },
                "summary": "Unified test session",
            }
        )

        return TestSessionStartResponse(
            call_id=call.id,
            simulated_phone=simulated_phone,
            started_at=call.started_at,
            template_code=runtime.template_code,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

    async def finalize_test_session(
        self,
        *,
        call_id: UUID,
        template_code: Optional[str] = None,
        run_extraction: bool = True,
    ) -> TestSessionFinalizeResponse:
        call = await self.call_repo.get(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")

        now = now_tokyo_naive()
        if not call.started_at:
            call.started_at = now
        if not call.answered_at:
            call.answered_at = call.started_at
        if not call.ended_at:
            call.ended_at = now

        call.duration_seconds = self._compute_duration_seconds(call.started_at, call.ended_at)
        call.status = "completed"
        call.is_answered = True

        extra_data = call.extra_data or {}
        extra_data.setdefault("simulation", True)
        extra_data.setdefault("source", "test_lab")
        if template_code:
            extra_data["template_code"] = template_code
        extra_data["finalized_at"] = now.isoformat()
        call.extra_data = extra_data

        await self.db.commit()
        await self.db.refresh(call)

        extraction_result: Optional[ExtractionResponse] = None
        appointment_id = None
        already_extracted = False

        if run_extraction:
            appointment_id, extraction_result, already_extracted = await self.extraction_bridge.resolve_finalized_call(
                call=call,
                template_code=template_code,
            )

        return TestSessionFinalizeResponse(
            call_id=call.id,
            status=call.status,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds or 0,
            appointment_id=appointment_id,
            extraction=extraction_result,
            already_extracted=already_extracted,
        )
