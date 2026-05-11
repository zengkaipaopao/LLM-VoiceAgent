"""
Test session lifecycle service for the test lab flows.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_defaults import require_generate_model, require_live_model
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ChatMessage,
    TestSessionAppendMessagesResponse,
    ExtractionResponse,
    TestSessionFinalizeResponse,
    TestSessionStartResponse,
)
from app.services.extraction_bridge import ExtractAppointmentRunner, ExtractionBridgeService
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.transcript_sanitizer import sanitize_assistant_turn
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

    @staticmethod
    def _normalize_test_mode(mode: str | None) -> str:
        token = (mode or "text").strip().lower()
        return "voice" if token == "voice" else "text"

    @staticmethod
    def _normalize_message_entries(raw_messages: list[ChatMessage] | list[dict[str, str]] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in raw_messages or []:
            if isinstance(item, ChatMessage):
                role_raw = item.role
                content_raw = item.content
            elif isinstance(item, dict):
                role_raw = str(item.get("role", ""))
                content_raw = str(item.get("content", ""))
            else:
                continue

            role = role_raw.strip().lower()
            if role not in {"user", "assistant", "system"}:
                continue
            content = content_raw.strip()
            if role == "assistant":
                content = sanitize_assistant_turn(content).strip()
            if not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
        mode: str = "text",
    ) -> TestSessionStartResponse:
        normalized_mode = self._normalize_test_mode(mode)
        runtime = await resolve_prompt_runtime(
            self.prompt_service,
            template_code=template_code,
            default_code=template_code,
            model_capability="live" if normalized_mode == "voice" else "generate",
        )
        template = runtime.template
        if not template:
            raise ValueError(f"Template '{template_code}' not found")

        llm_provider = provider or runtime.llm_provider or "gemini"
        if normalized_mode == "voice":
            llm_model = require_live_model(
                model or runtime.llm_model,
                source="Prompt llm_model",
            )
        else:
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
                    "test_mode": normalized_mode,
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

    async def append_test_session_messages(
        self,
        *,
        call_id: UUID,
        messages: list[ChatMessage] | list[dict[str, str]],
        template_code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TestSessionAppendMessagesResponse:
        call = await self.call_repo.get(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")

        normalized_entries = self._normalize_message_entries(messages)
        extra_data = dict(call.extra_data or {})
        stored_messages = self._normalize_message_entries(extra_data.get("messages") or [])
        stored_messages.extend(normalized_entries)
        extra_data["messages"] = stored_messages
        if template_code:
            extra_data["template_code"] = template_code
        if provider:
            extra_data["llm_provider"] = provider
        if model:
            extra_data["llm_model"] = model

        transcript_lines: list[str] = []
        for item in normalized_entries:
            if item["role"] == "system":
                continue
            speaker = "用户" if item["role"] == "user" else "助手"
            transcript_lines.append(f"{speaker}: {item['content']}")

        transcript_update = call.transcript or ""
        if transcript_lines:
            block = "\n".join(transcript_lines)
            transcript_update = f"{transcript_update}\n\n{block}" if transcript_update else block

        call.extra_data = extra_data
        call.transcript = transcript_update

        await self.db.commit()
        await self.db.refresh(call)

        return TestSessionAppendMessagesResponse(
            call_id=call.id,
            appended_count=len(normalized_entries),
            transcript_length=len(call.transcript or ""),
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

        extra_data = dict(call.extra_data or {})
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
            final_extra_data = dict(call.extra_data or {})
            final_extra_data["appointment_id"] = str(appointment_id) if appointment_id else None
            final_extra_data["already_extracted"] = already_extracted
            if extraction_result:
                final_extra_data["extraction_status"] = "success" if extraction_result.success else "failed"
                final_extra_data["extraction_message"] = extraction_result.message
                final_extra_data["extraction_confidence"] = extraction_result.confidence
            call.extra_data = final_extra_data
            await self.db.commit()
            await self.db.refresh(call)
        else:
            final_extra_data = dict(call.extra_data or {})
            final_extra_data["extraction_status"] = "skipped"
            call.extra_data = final_extra_data
            await self.db.commit()
            await self.db.refresh(call)

        return TestSessionFinalizeResponse(
            call_id=call.id,
            status=call.status,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds or 0,
            appointment_id=appointment_id,
            extraction=extraction_result,
            already_extracted=already_extracted,
        )
