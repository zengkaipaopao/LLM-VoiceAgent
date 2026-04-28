"""
Chat service for LLM orchestrations and extracting data.
"""
import json
import random
import re
from datetime import datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID

import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.model_defaults import require_generate_model, resolve_generate_model
from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse,
    TestSessionOperationTurnResponse,
    TestSessionFinalizeResponse,
    TestSessionStartResponse,
)
from app.services.appointments.operation_executor import AppointmentOperationExecutor
from app.services.appointments.operation_flow import AppointmentOperationFlowService
from app.services.appointments.operation_matcher import AppointmentOperationMatcher
from app.services.appointments.parsers import JapaneseAppointmentParser
from app.services.appointments.presenter import AppointmentBriefPresenter
from app.services.chat_runtime_service import ChatRuntimeService
from app.services.extraction_service import ExtractionService
from app.services.llm.exceptions import LLMRateLimitError
from app.services.llm.factory import LLMFactory
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.test_session_service import TestSessionService
from app.services.transcript_sanitizer import find_injected_user_turn_start, sanitize_assistant_turn
from app.utils.datetime_utils import now_tokyo_naive


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ChatService:
    """Service for handling chat orchestration and appointment extraction."""
    _OP_FLOW_KEY = "appointment_operation_flow"

    _ASSISTANT_PREFIX_PATTERN = re.compile(
        r"^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
        flags=re.IGNORECASE,
    )
    _ASSISTANT_INLINE_PREFIX_PATTERN = re.compile(
        r"(?im)(?:^|\n)\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
    )
    _INJECTED_USER_TURN_PATTERN = re.compile(
        r"(?im)(?:^|\n)\s*(?:user|customer|human|用户|お客様)\s*[:：]",
    )
    _JP_OPENING_GREETING = (
        "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
    )

    def __init__(self, db: AsyncSession):
        self.db = db
        self.call_repo = CallRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.prompt_service = PromptService(db)

    @staticmethod
    def _generate_simulated_phone() -> str:
        """Generate a JP-style simulated phone number in E.164 format."""
        prefix = random.choice(["70", "80", "90"])
        subscriber = "".join(str(random.randint(0, 9)) for _ in range(8))
        return f"+81{prefix}{subscriber}"

    @staticmethod
    def _compute_duration_seconds(started_at: Optional[datetime], ended_at: Optional[datetime]) -> int:
        if not started_at or not ended_at:
            return 0
        return max(0, int((ended_at - started_at).total_seconds()))

    @staticmethod
    def _extract_retry_delay_seconds(error_message: str) -> Optional[int]:
        match = re.search(r"retry in\s+([0-9.]+)s", error_message, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return max(1, int(float(match.group(1))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _looks_like_quota_error(error_message: str) -> bool:
        lowered = error_message.lower()
        keywords = ["429", "quota", "resource_exhausted", "rate limit", "too many requests"]
        return any(keyword in lowered for keyword in keywords)

    @classmethod
    def _build_quota_notice_reply(cls, error_message: str, *, api_key_missing: bool = False) -> str:
        if api_key_missing:
            return (
                "⚠️ 当前未配置 Gemini API Key，暂时无法调用真实模型。"
                "请在后端 .env 中配置可用 Key 后重试。"
            )

        retry_seconds = cls._extract_retry_delay_seconds(error_message)
        retry_text = f"建议约 {retry_seconds} 秒后重试。" if retry_seconds else "请稍后重试。"
        return (
            "⚠️ 当前 Gemini 配额不足（429 RESOURCE_EXHAUSTED），暂时无法调用真实模型。"
            f"{retry_text} 请检查 Google AI Studio 项目的配额与计费设置。"
        )

    @classmethod
    def _sanitize_assistant_response(cls, text: str) -> str:
        return sanitize_assistant_turn(text)

    @classmethod
    def _extract_leading_sentence(cls, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return ""

        first_line = normalized.splitlines()[0].strip() or normalized
        sentence_match = re.match(r"^(.+?[。！？!?])", first_line)
        if sentence_match:
            return sentence_match.group(1).strip()
        return first_line[:80].strip()

    @classmethod
    def _strip_redundant_opening_greeting(
        cls,
        text: str,
        *,
        prior_assistant_messages: list[str],
    ) -> str:
        if not text:
            return ""
        normalized = text.strip()
        if not prior_assistant_messages:
            return normalized

        candidates: list[str] = [cls._JP_OPENING_GREETING]
        for prior in prior_assistant_messages:
            prior_clean = cls._sanitize_assistant_response(prior)
            if not prior_clean:
                continue
            first_line = prior_clean.splitlines()[0].strip()
            if first_line:
                candidates.append(first_line)
            leading_sentence = cls._extract_leading_sentence(prior_clean)
            if leading_sentence:
                candidates.append(leading_sentence)
            break

        unique_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in sorted(candidates, key=len, reverse=True):
            token = candidate.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            unique_candidates.append(token)

        for candidate in unique_candidates:
            if not normalized.startswith(candidate):
                continue
            trimmed = normalized[len(candidate):].lstrip()
            trimmed = re.sub(r"^[\s、，。:：\-]+", "", trimmed).lstrip()
            return trimmed or normalized

        return normalized

    @classmethod
    def _find_injected_user_turn_start(cls, text: str) -> Optional[int]:
        return find_injected_user_turn_start(text)

    @classmethod
    def _normalize_messages(cls, raw_messages: Any) -> list[dict[str, str]]:
        """Normalize stored messages into a safe role/content list."""
        if not isinstance(raw_messages, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role_raw = str(item.get("role", "")).strip().lower()
            role = {
                "human": "user",
                "customer": "user",
                "ai": "assistant",
                "bot": "assistant",
                "model": "assistant",
                "助手": "assistant",
                "アシスタント": "assistant",
            }.get(role_raw, role_raw)
            if role not in {"user", "assistant", "system"}:
                continue
            content = str(item.get("content", "")).strip()
            if role == "assistant":
                content = cls._sanitize_assistant_response(content).strip()
            if not role or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    @classmethod
    def _parse_messages_from_transcript(cls, transcript: Optional[str]) -> list[dict[str, str]]:
        """Fallback: parse transcript text into message list."""
        if not transcript:
            return []

        pattern = re.compile(r"(用户|助手):\s*(.*?)(?=\n(?:用户|助手):\s*|\Z)", flags=re.S)
        parsed: list[dict[str, str]] = []
        for speaker, content in pattern.findall(transcript):
            cleaned = content.strip()
            if speaker == "助手":
                cleaned = cls._sanitize_assistant_response(cleaned).strip()
            if not cleaned:
                continue
            parsed.append(
                {
                    "role": "user" if speaker == "用户" else "assistant",
                    "content": cleaned,
                }
            )
        return parsed

    @staticmethod
    def _resolve_chat_response_mode(call: Call, template: Any) -> tuple[str, Optional[dict[str, Any]]]:
        """
        Decide runtime response format for chat.

        Unified test tab expects conversational text, so force text mode there
        even if prompt template has json_object configured for extraction workflows.
        """
        response_format = getattr(template, "response_format", None) or "text"
        output_schema = getattr(template, "output_schema", None)

        source = (call.extra_data or {}).get("source")
        if source == "test_lab" and response_format == "json_object":
            return "text", None

        return response_format, output_schema

    async def _resolve_extracted_operation_target(
        self,
        *,
        call: Call,
        raw_data: dict[str, Any],
    ) -> Optional[Appointment]:
        return await self._build_operation_matcher().resolve_extracted_operation_target(
            call=call,
            raw_data=raw_data,
        )

    async def _try_apply_extracted_operation_request(
        self,
        *,
        call: Call,
        raw_data: dict[str, Any],
        extraction_summary: str,
        extraction_confidence: float,
        extra_data: dict[str, Any],
    ) -> Optional[ExtractionResponse]:
        operation = self._extract_operation_type_from_raw_data(raw_data)
        if operation not in {"cancel", "update"}:
            return None

        target = await self._resolve_extracted_operation_target(call=call, raw_data=raw_data)
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

        pending_changes = self._build_update_changes_from_extraction(raw_data) if operation == "update" else {}
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

        await self._execute_operation_flow_action(
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
        operation_event_id: Optional[UUID] = None
        if isinstance(operation_execution, dict):
            try:
                operation_event_id = UUID(str(operation_execution.get("appointment_id")))
            except (TypeError, ValueError):
                operation_event_id = None

        return ExtractionResponse(
            success=True,
            appointment_id=operation_event_id,
            extracted_data={
                "operation": operation,
                "target_appointment_id": str(target.id),
                "operation_event_id": str(operation_event_id) if operation_event_id else None,
                "changes": pending_changes,
                "resolution_status": "executed_from_llm_extraction",
                "extracted_data": raw_data,
            },
            confidence=extraction_confidence,
            message="检测到预约变更/取消请求，已更新目标预约并创建操作事件",
        )

    async def _execute_operation_flow_action(
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
        return await self._build_operation_executor().execute(
            call=call,
            appointment=appointment,
            operation=operation,
            pending_changes=pending_changes,
            flow=flow,
            extra_data=extra_data,
            user_message=user_message,
        )

    async def _find_operation_candidates(
        self,
        call: Call,
        user_message: str,
        *,
        base_hints: Optional[dict[str, str]] = None,
        expected_identity_key: Optional[str] = None,
    ) -> tuple[list[Appointment], dict[str, str]]:
        return await self._build_operation_matcher().find_candidates(
            call,
            user_message,
            base_hints=base_hints,
            expected_identity_key=expected_identity_key,
        )

    async def _load_operation_candidates_by_ids(self, candidate_ids: list[str]) -> list[Appointment]:
        return await self._build_operation_matcher().load_candidates_by_ids(candidate_ids)

    async def _handle_appointment_operation_flow(self, call: Call, user_message: str) -> Optional[str]:
        return await self._build_operation_flow_service().handle(call, user_message)

    # Appointment-domain parsing and presentation helpers live outside this facade.
    # Keep private aliases temporarily so existing internal calls/tests stay stable
    # while ChatService is reduced in phases.
    _parse_appointment_time = staticmethod(JapaneseAppointmentParser.parse_appointment_time)
    _first_non_empty = staticmethod(JapaneseAppointmentParser.first_non_empty)
    _extract_amount_from_text = staticmethod(JapaneseAppointmentParser.extract_amount_from_text)
    _resolve_amount = staticmethod(JapaneseAppointmentParser.resolve_amount)
    _resolve_address = staticmethod(JapaneseAppointmentParser.resolve_address)
    _resolve_extra_request = staticmethod(JapaneseAppointmentParser.resolve_extra_request)
    _resolve_category = staticmethod(JapaneseAppointmentParser.resolve_category)
    _normalize_datetime_text = staticmethod(JapaneseAppointmentParser.normalize_datetime_text)
    _parse_optional_appointment_time = staticmethod(JapaneseAppointmentParser.parse_optional_appointment_time)
    _extract_operation_type_from_raw_data = staticmethod(JapaneseAppointmentParser.extract_operation_type_from_raw_data)
    _is_cancelled_appointment = staticmethod(JapaneseAppointmentParser.is_cancelled_appointment)
    _build_update_changes_from_extraction = staticmethod(JapaneseAppointmentParser.build_update_changes_from_extraction)
    _score_extracted_operation_candidate = staticmethod(JapaneseAppointmentParser.score_extracted_operation_candidate)
    _detect_operation_intent = staticmethod(JapaneseAppointmentParser.detect_operation_intent)
    _normalize_identity_token = staticmethod(JapaneseAppointmentParser.normalize_identity_token)
    _is_generic_caller_name = staticmethod(JapaneseAppointmentParser.is_generic_caller_name)
    _is_placeholder_counterpart = staticmethod(JapaneseAppointmentParser.is_placeholder_counterpart)
    _is_affirmative = staticmethod(JapaneseAppointmentParser.is_affirmative)
    _is_negative = staticmethod(JapaneseAppointmentParser.is_negative)
    _extract_target_date = staticmethod(JapaneseAppointmentParser.extract_target_date)
    _extract_datetime_parts_from_text = staticmethod(JapaneseAppointmentParser.extract_datetime_parts_from_text)
    _extract_datetime_from_text = staticmethod(JapaneseAppointmentParser.extract_datetime_from_text)
    _extract_address_from_text = staticmethod(JapaneseAppointmentParser.extract_address_from_text)
    _extract_update_changes = staticmethod(JapaneseAppointmentParser.extract_update_changes)
    _normalize_phone_number = staticmethod(JapaneseAppointmentParser.normalize_phone_number)
    _normalize_match_text = staticmethod(JapaneseAppointmentParser.normalize_match_text)
    _loosely_matches = staticmethod(JapaneseAppointmentParser.loosely_matches)
    _extract_company_hint = staticmethod(JapaneseAppointmentParser.extract_company_hint)
    _extract_company_hint_from_expected_reply = staticmethod(JapaneseAppointmentParser.extract_company_hint_from_expected_reply)
    _extract_name_hint_from_expected_reply = staticmethod(JapaneseAppointmentParser.extract_name_hint_from_expected_reply)
    _extract_company_name_pair = staticmethod(JapaneseAppointmentParser.extract_company_name_pair)
    _extract_name_hint = staticmethod(JapaneseAppointmentParser.extract_name_hint)
    _extract_phone_hint = staticmethod(JapaneseAppointmentParser.extract_phone_hint)
    _collect_operation_identity_hints = staticmethod(JapaneseAppointmentParser.collect_operation_identity_hints)
    _count_operation_identity_hints = staticmethod(JapaneseAppointmentParser.count_operation_identity_hints)
    _parse_hint_date = staticmethod(JapaneseAppointmentParser.parse_hint_date)
    _score_operation_candidate = staticmethod(JapaneseAppointmentParser.score_operation_candidate)
    _next_identity_question_key = staticmethod(JapaneseAppointmentParser.next_identity_question_key)
    _build_identity_single_question = staticmethod(JapaneseAppointmentParser.build_identity_single_question)
    _build_operation_identity_prompt = staticmethod(JapaneseAppointmentParser.build_operation_identity_prompt)
    _format_brief_value = staticmethod(AppointmentBriefPresenter.format_value)
    _resolve_appointment_brief_category = staticmethod(AppointmentBriefPresenter.resolve_category)
    _resolve_appointment_brief_amount = staticmethod(AppointmentBriefPresenter.resolve_amount)
    _format_appointment_brief = staticmethod(AppointmentBriefPresenter.format_appointment_brief)
    _build_operation_conversation_snapshot = staticmethod(AppointmentOperationExecutor.build_conversation_snapshot)
    _build_operation_event_summary = staticmethod(AppointmentOperationExecutor.build_event_summary)
    _select_candidate_id_from_text = staticmethod(AppointmentOperationFlowService.select_candidate_id_from_text)
    _build_disambiguation_question = staticmethod(AppointmentOperationFlowService.build_disambiguation_question)
    _choose_disambiguation_field = staticmethod(AppointmentOperationFlowService.choose_disambiguation_field)
    _extract_disambiguation_answer = staticmethod(AppointmentOperationFlowService.extract_disambiguation_answer)
    _candidate_matches_disambiguation = staticmethod(
        AppointmentOperationFlowService.candidate_matches_disambiguation
    )

    async def _resolve_template(self, template_code: str):
        template = await self.prompt_service.get_template(template_code)
        if not template and template_code != "general_appointment":
            raise ValueError(f"Template '{template_code}' not found")
        return template

    def _build_chat_runtime_service(self) -> ChatRuntimeService:
        return ChatRuntimeService(
            self.db,
            call_repo=self.call_repo,
            prompt_service=self.prompt_service,
            normalize_messages=self._normalize_messages,
        )

    def _build_test_session_service(self) -> TestSessionService:
        return TestSessionService(
            self.db,
            call_repo=self.call_repo,
            appointment_repo=self.appointment_repo,
            prompt_service=self.prompt_service,
            extract_appointment=self.extract_appointment,
        )

    def _build_operation_executor(self) -> AppointmentOperationExecutor:
        return AppointmentOperationExecutor(
            self.db,
            appointment_repo=self.appointment_repo,
            flow_key=self._OP_FLOW_KEY,
        )

    def _build_operation_matcher(self) -> AppointmentOperationMatcher:
        return AppointmentOperationMatcher(self.appointment_repo)

    def _build_operation_flow_service(self) -> AppointmentOperationFlowService:
        return AppointmentOperationFlowService(
            appointment_repo=self.appointment_repo,
            matcher=self._build_operation_matcher(),
            executor=self._build_operation_executor(),
            flow_key=self._OP_FLOW_KEY,
        )

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> TestSessionStartResponse:
        return await self._build_test_session_service().start_test_session(
            template_code=template_code,
            provider=provider,
            model=model,
            caller_name=caller_name,
        )

    async def finalize_test_session(
        self,
        *,
        call_id: UUID,
        template_code: Optional[str] = None,
        run_extraction: bool = True,
    ) -> TestSessionFinalizeResponse:
        return await self._build_test_session_service().finalize_test_session(
            call_id=call_id,
            template_code=template_code,
            run_extraction=run_extraction,
        )

    async def get_or_create_call(self, call_id: Optional[UUID] = None) -> Call:
        """Get existing call or create a new one."""
        return await self._build_chat_runtime_service().get_or_create_call(call_id)

    async def _setup_chat_context(self, request: ChatRequest, call: Call) -> dict[str, Any]:
        """Setup context for a chat message including templates and LLM client."""
        return await self._build_chat_runtime_service().setup_chat_context(request, call)

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a single chat request and return a response."""
        chat_runtime = self._build_chat_runtime_service()
        call = await chat_runtime.get_or_create_call(request.call_id)
        context = await chat_runtime.setup_chat_context(request, call)

        template = context["template"]
        llm_service = context["llm_service"]
        messages = context["messages"]
        system_prompt = context["system_prompt"]
        prior_assistant_messages = [
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") == "assistant" and str(item.get("content", "")).strip()
        ]

        messages.append({"role": "user", "content": request.message})

        temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
        resp_format, out_schema = self._resolve_chat_response_mode(call, template)
        quota_notice_reason: Optional[str] = None

        operation_flow_response = await self._handle_appointment_operation_flow(call, request.message)
        if operation_flow_response is not None:
            response = operation_flow_response
        elif not settings.google_genai_backend_enabled:
            if not settings.llm_show_quota_notice_as_reply:
                raise ValueError("Gemini backend not configured. Please check backend/.env")
            response = self._build_quota_notice_reply(
                "Gemini backend not configured",
                api_key_missing=True,
            )
            quota_notice_reason = "Gemini backend not configured"
        else:
            try:
                response = await llm_service.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    response_format=resp_format,
                    output_schema=out_schema,
                )
            except LLMRateLimitError as rate_limit_error:
                if not settings.llm_show_quota_notice_as_reply:
                    raise
                quota_notice_reason = str(rate_limit_error)
                response = self._build_quota_notice_reply(quota_notice_reason)
            except Exception as llm_error:
                if not settings.llm_show_quota_notice_as_reply or not self._looks_like_quota_error(str(llm_error)):
                    raise
                quota_notice_reason = str(llm_error)
                response = self._build_quota_notice_reply(quota_notice_reason)

        response = self._sanitize_assistant_response(response)
        response = self._strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )
        messages.append({"role": "assistant", "content": response})
        await chat_runtime.persist_turn(
            call=call,
            user_message=request.message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=quota_notice_reason,
        )

        input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
        total_tokens = count_tokens(input_text) + count_tokens(response)

        return ChatResponse(response=response, call_id=call.id, tokens_used=total_tokens)

    async def process_test_session_operation_turn(
        self,
        *,
        call_id: UUID,
        message: str,
        template_code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TestSessionOperationTurnResponse:
        """Advance test session through operation flow only, without generic LLM fallback."""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message cannot be empty")

        chat_runtime = self._build_chat_runtime_service()
        call = await chat_runtime.get_or_create_call(call_id)
        extra_data = dict(call.extra_data or {})
        messages = self._normalize_messages(extra_data.get("messages"))
        if not messages:
            messages = self._parse_messages_from_transcript(call.transcript)
        prior_assistant_messages = [
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") == "assistant" and str(item.get("content", "")).strip()
        ]
        context = {
            "template_code": template_code or extra_data.get("template_code") or "general_appointment",
            "llm_provider": provider or extra_data.get("llm_provider") or "gemini",
            "llm_model": model or extra_data.get("llm_model") or "",
        }

        response = await self._handle_appointment_operation_flow(call, normalized_message)
        if response is None:
            flow = dict((call.extra_data or {}).get(self._OP_FLOW_KEY) or {})
            return TestSessionOperationTurnResponse(
                call_id=call.id,
                handled=False,
                operation=str(flow.get("operation") or "") or None,
                state_status=str(flow.get("status") or "") or None,
                executed=isinstance((call.extra_data or {}).get("operation_execution"), dict),
            )

        response = self._sanitize_assistant_response(response)
        response = self._strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )

        messages.append({"role": "user", "content": normalized_message})
        messages.append({"role": "assistant", "content": response})
        await chat_runtime.persist_turn(
            call=call,
            user_message=normalized_message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=None,
        )

        refreshed_extra_data = dict(call.extra_data or {})
        flow = dict(refreshed_extra_data.get(self._OP_FLOW_KEY) or {})
        operation_execution = refreshed_extra_data.get("operation_execution")
        executed = isinstance(operation_execution, dict)
        operation = None
        if executed:
            operation = str(operation_execution.get("operation") or "") or None
        if not operation:
            operation = str(flow.get("operation") or "") or None

        return TestSessionOperationTurnResponse(
            call_id=call.id,
            handled=True,
            response=response,
            operation=operation,
            state_status=str(flow.get("status") or "") or None,
            executed=executed,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Process a chat request and stream the response via SSE."""
        try:
            chat_runtime = self._build_chat_runtime_service()
            call = await chat_runtime.get_or_create_call(request.call_id)

            if not request.call_id:
                yield f"data: {json.dumps({'type': 'call_id', 'call_id': str(call.id)})}\n\n"

            context = await chat_runtime.setup_chat_context(request, call)
            template = context["template"]
            llm_service = context["llm_service"]
            messages = context["messages"]
            system_prompt = context["system_prompt"]
            prior_assistant_messages = [
                str(item.get("content", "")).strip()
                for item in messages
                if item.get("role") == "assistant" and str(item.get("content", "")).strip()
            ]

            messages.append({"role": "user", "content": request.message})

            temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
            resp_format, out_schema = self._resolve_chat_response_mode(call, template)

            full_response = ""
            quota_notice_reason: Optional[str] = None

            operation_flow_response = await self._handle_appointment_operation_flow(call, request.message)
            if operation_flow_response is not None:
                full_response = operation_flow_response
                yield f"data: {json.dumps({'type': 'content', 'content': full_response})}\n\n"
            elif not settings.google_genai_backend_enabled:
                if not settings.llm_show_quota_notice_as_reply:
                    raise ValueError("Gemini backend not configured. Please check backend/.env")
                quota_notice_reason = "Gemini backend not configured"
                full_response = self._build_quota_notice_reply(quota_notice_reason, api_key_missing=True)
                yield f"data: {json.dumps({'type': 'content', 'content': full_response})}\n\n"
            else:
                try:
                    async for chunk in llm_service.chat_stream(
                        messages=messages,
                        temperature=temperature,
                        response_format=resp_format,
                        output_schema=out_schema,
                    ):
                        candidate_response = f"{full_response}{chunk}"
                        injected_turn_start = self._find_injected_user_turn_start(candidate_response)

                        if injected_turn_start is not None:
                            # Stream only the safe part before model-injected "User: ..." content.
                            safe_response = candidate_response[:injected_turn_start]
                            safe_delta = safe_response[len(full_response):]
                            full_response = safe_response
                            if safe_delta:
                                yield f"data: {json.dumps({'type': 'content', 'content': safe_delta})}\n\n"
                            break

                        full_response = candidate_response
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                except LLMRateLimitError as rate_limit_error:
                    if not settings.llm_show_quota_notice_as_reply:
                        raise
                    quota_notice_reason = str(rate_limit_error)
                    notice = self._build_quota_notice_reply(quota_notice_reason)
                    if full_response:
                        full_response = f"{full_response}\n\n{notice}"
                    else:
                        full_response = notice
                    yield f"data: {json.dumps({'type': 'content', 'content': notice})}\n\n"
                except Exception as llm_error:
                    if not settings.llm_show_quota_notice_as_reply or not self._looks_like_quota_error(str(llm_error)):
                        raise
                    quota_notice_reason = str(llm_error)
                    notice = self._build_quota_notice_reply(quota_notice_reason)
                    if full_response:
                        full_response = f"{full_response}\n\n{notice}"
                    else:
                        full_response = notice
                    yield f"data: {json.dumps({'type': 'content', 'content': notice})}\n\n"

            full_response = self._sanitize_assistant_response(full_response)
            full_response = self._strip_redundant_opening_greeting(
                full_response,
                prior_assistant_messages=prior_assistant_messages,
            )
            messages.append({"role": "assistant", "content": full_response})
            await chat_runtime.persist_turn(
                call=call,
                user_message=request.message,
                assistant_message=full_response,
                context=context,
                messages=messages,
                quota_notice_reason=quota_notice_reason,
                refresh_call=False,
            )

            input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
            total_tokens = count_tokens(input_text) + count_tokens(full_response)

            yield f"data: {json.dumps({'type': 'done', 'call_id': str(call.id), 'tokens_used': total_tokens})}\n\n"

        except ValueError as ve:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ve)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def extract_appointment(self, request: ExtractionRequest) -> ExtractionResponse:
        """Extract appointment details from a completed chat call."""
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

            extra_data = call.extra_data or {}
            operation_execution = extra_data.get("operation_execution")
            if isinstance(operation_execution, dict):
                op_type = str(operation_execution.get("operation") or "").lower()
                appt_id = operation_execution.get("appointment_id")
                if op_type in {"update", "cancel"} and appt_id:
                    try:
                        resolved_id = UUID(str(appt_id))
                    except (TypeError, ValueError):
                        resolved_id = None
                    if resolved_id:
                        return ExtractionResponse(
                            success=True,
                            appointment_id=resolved_id,
                            extracted_data=operation_execution,
                            confidence=1.0,
                            message="检测到本次会话已完成预约变更/取消，跳过新建提取",
                        )

            messages = self._normalize_messages(extra_data.get("messages"))
            if not messages:
                messages = self._parse_messages_from_transcript(call.transcript)
                if messages:
                    extra_data["messages"] = messages
                    call.extra_data = dict(extra_data)
                    await self.db.commit()

            if not messages:
                raise ValueError("No conversation found in call")

            template_code = request.template_code or extra_data.get("template_code", "general_appointment")
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

            raw_data = extraction_result.raw_data or {}
            operation_resolution = await self._try_apply_extracted_operation_request(
                call=call,
                raw_data=raw_data,
                extraction_summary=extraction_result.summary or extraction_result.appointment_content,
                extraction_confidence=extraction_result.confidence,
                extra_data=dict(extra_data),
            )
            if operation_resolution is not None:
                return operation_resolution

            appt_time = self._parse_appointment_time(extraction_result.appointment_time)
            resolved_amount = self._resolve_amount(
                raw_data,
                extraction_result.summary,
                extraction_result.appointment_content,
                call.transcript,
                "\n".join(
                    str(message.get("content", "")).strip()
                    for message in messages
                    if isinstance(message, dict) and str(message.get("content", "")).strip()
                ),
            )
            resolved_address = self._resolve_address(raw_data)
            resolved_extra_request = self._resolve_extra_request(raw_data)
            resolved_category = self._resolve_category(extraction_result.category, raw_data)

            appointment_extra_data = {
                "simulation": bool(extra_data.get("simulation", False)),
                "source": extra_data.get("source", "chat"),
                "simulated_phone": extra_data.get("simulated_phone"),
                "llm_provider": llm_provider,
                "llm_model": llm_model,
            }

            appt_data = dict(
                call_id=call.id,
                timestamp=now_tokyo_naive(),
                caller_name=extraction_result.caller_name or call.caller_name or "Unknown",
                company=extraction_result.company,
                appointment=appt_time,
                category=resolved_category,
                amount=resolved_amount,
                address=resolved_address,
                summary=extraction_result.summary or extraction_result.appointment_content or "提取的预约信息",
                extra_request=resolved_extra_request,
                operation="create",
                prompt_id=template.id if template else None,
                type_name=template.category if template else "general",
                extracted_data=raw_data,
                extra_data=appointment_extra_data,
                raw_messages={
                    "extraction_source": "llm_chat",
                    "template_code": template_code,
                    "confidence": extraction_result.confidence,
                    "conversation": messages,
                    "extracted_data": raw_data,
                },
            )

            appointment = await self.appointment_repo.create(appt_data)

            return ExtractionResponse(
                success=True,
                appointment_id=appointment.id,
                extracted_data=extraction_result.model_dump(),
                confidence=extraction_result.confidence,
                message="预约信息提取成功",
            )
        except Exception as e:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={},
                confidence=0.0,
                message=f"提取失败: {str(e)}",
            )
