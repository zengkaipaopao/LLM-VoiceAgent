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
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse,
    TestSessionFinalizeResponse,
    TestSessionStartResponse,
)
from app.services.extraction_service import ExtractionService
from app.services.llm.exceptions import LLMRateLimitError
from app.services.llm.factory import LLMFactory
from app.services.prompt_service import PromptService
from app.utils.datetime_utils import now_tokyo_naive, to_tokyo_naive


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ChatService:
    """Service for handling chat orchestration and appointment extraction."""

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

    @classmethod
    def _parse_appointment_time(cls, value: Optional[str]) -> datetime:
        if not value:
            return now_tokyo_naive()

        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return to_tokyo_naive(parsed) or now_tokyo_naive()

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

    async def _resolve_template(self, template_code: str):
        template = await self.prompt_service.get_template(template_code)
        if not template and template_code != "general_appointment":
            raise ValueError(f"Template '{template_code}' not found")
        return template

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> TestSessionStartResponse:
        """Create a unified test session with a simulated phone number."""
        template = await self.prompt_service.get_template(template_code)
        if not template:
            raise ValueError(f"Template '{template_code}' not found")

        llm_provider = provider or getattr(template, "llm_provider", None) or "gemini"
        llm_model = model or getattr(template, "llm_model", None) or settings.default_llm_model

        started_at = now_tokyo_naive()
        simulated_phone = self._generate_simulated_phone()

        extra_data = {
            "simulation": True,
            "source": "test_lab",
            "simulated_phone": simulated_phone,
            "template_code": template_code,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "messages": [],
        }

        call_data = {
            "direction": "inbound",
            "counterpart": simulated_phone,
            "caller_name": caller_name or "Test Caller",
            "status": "ongoing",
            "handler_type": "ai",
            "is_answered": True,
            "started_at": started_at,
            "answered_at": started_at,
            "prompt_id": template.id,
            "extra_data": extra_data,
            "summary": "Unified test session",
        }

        call = await self.call_repo.create(call_data)

        return TestSessionStartResponse(
            call_id=call.id,
            simulated_phone=simulated_phone,
            started_at=call.started_at,
            template_code=template_code,
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
        """Finalize call lifecycle and optionally extract appointment (idempotent)."""
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
            existing = await self.appointment_repo.get_by_call_id(call.id)
            if existing:
                already_extracted = True
                appointment_id = existing.id
                extraction_result = ExtractionResponse(
                    success=True,
                    appointment_id=existing.id,
                    extracted_data=existing.extracted_data or {},
                    confidence=1.0,
                    message="已有预约记录，跳过重复提取",
                )
            else:
                extraction_request = ExtractionRequest(
                    call_id=call.id,
                    template_code=template_code or extra_data.get("template_code"),
                )
                extraction_result = await self.extract_appointment(extraction_request)
                appointment_id = extraction_result.appointment_id

        return TestSessionFinalizeResponse(
            call_id=call.id,
            status=call.status,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds or 0,
            appointment_id=appointment_id,
            extraction=extraction_result,
            already_extracted=already_extracted,
        )

    async def get_or_create_call(self, call_id: Optional[UUID] = None) -> Call:
        """Get existing call or create a new one."""
        if call_id:
            call = await self.call_repo.get(call_id)
            if not call:
                raise ValueError(f"Call {call_id} not found")
            return call

        call_data = {
            "direction": "inbound",
            "counterpart": "chat_user",
            "status": "ongoing",
            "handler_type": "ai",
        }
        return await self.call_repo.create(call_data)

    async def _setup_chat_context(self, request: ChatRequest, call: Call) -> dict[str, Any]:
        """Setup context for a chat message including templates and LLM client."""
        extra_data = call.extra_data or {}
        if request.template_code and request.template_code != "general_appointment":
            resolved_template_code = request.template_code
        else:
            resolved_template_code = extra_data.get("template_code", request.template_code)

        template = await self._resolve_template(resolved_template_code)

        llm_provider = (
            request.provider
            or extra_data.get("llm_provider")
            or getattr(template, "llm_provider", None)
            or "gemini"
        )
        llm_model = (
            request.model
            or extra_data.get("llm_model")
            or getattr(template, "llm_model", None)
            or settings.default_llm_model
        )

        llm_service = LLMFactory.create(
            provider=llm_provider,
            api_key=settings.google_api_key,
            model=llm_model,
        )

        messages = extra_data.get("messages", [])

        system_prompt = ""
        if template:
            system_prompt = self.prompt_service.render_prompt(
                template,
                {"current_time": now_tokyo_naive().isoformat()},
            )
        else:
            system_prompt = f"""
            You are an AI assistant for appointment booking.
            Current time: {now_tokyo_naive().isoformat()}
            User wants to book an appointment.
            Extract: name, time, purpose.
            """

        if not messages:
            messages.append({"role": "system", "content": system_prompt})

        return {
            "template": template,
            "llm_service": llm_service,
            "messages": messages,
            "system_prompt": system_prompt,
            "template_code": resolved_template_code,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        }

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a single chat request and return a response."""
        call = await self.get_or_create_call(request.call_id)
        context = await self._setup_chat_context(request, call)

        template = context["template"]
        llm_service = context["llm_service"]
        messages = context["messages"]
        system_prompt = context["system_prompt"]

        messages.append({"role": "user", "content": request.message})

        temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
        resp_format = getattr(template, "response_format", None) or "text"
        out_schema = getattr(template, "output_schema", None)
        quota_notice_reason: Optional[str] = None

        if not settings.google_api_key:
            if not settings.llm_show_quota_notice_as_reply:
                raise ValueError("Google API Key not configured. Please check backend/.env")
            response = self._build_quota_notice_reply(
                "Google API Key not configured",
                api_key_missing=True,
            )
            quota_notice_reason = "Google API Key not configured"
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

        messages.append({"role": "assistant", "content": response})

        extra_data = call.extra_data or {}
        extra_data["messages"] = messages
        extra_data["template_code"] = context["template_code"]
        extra_data["llm_provider"] = context["llm_provider"]
        extra_data["llm_model"] = context["llm_model"]
        if quota_notice_reason:
            extra_data["llm_quota_notice"] = {
                "reason": quota_notice_reason,
                "timestamp": now_tokyo_naive().isoformat(),
            }
        else:
            extra_data.pop("llm_quota_notice", None)

        transcript_update = call.transcript or ""
        transcript_update += (
            f"\n\n用户: {request.message}\n助手: {response}"
            if transcript_update
            else f"用户: {request.message}\n助手: {response}"
        )

        call.extra_data = extra_data
        call.transcript = transcript_update

        await self.db.commit()
        await self.db.refresh(call)

        input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
        total_tokens = count_tokens(input_text) + count_tokens(response)

        return ChatResponse(response=response, call_id=call.id, tokens_used=total_tokens)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Process a chat request and stream the response via SSE."""
        try:
            call = await self.get_or_create_call(request.call_id)

            if not request.call_id:
                yield f"data: {json.dumps({'type': 'call_id', 'call_id': str(call.id)})}\n\n"

            context = await self._setup_chat_context(request, call)
            template = context["template"]
            llm_service = context["llm_service"]
            messages = context["messages"]
            system_prompt = context["system_prompt"]

            messages.append({"role": "user", "content": request.message})

            temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
            resp_format = getattr(template, "response_format", None) or "text"
            out_schema = getattr(template, "output_schema", None)

            full_response = ""
            quota_notice_reason: Optional[str] = None

            if not settings.google_api_key:
                if not settings.llm_show_quota_notice_as_reply:
                    raise ValueError("Google API Key not configured. Please check backend/.env")
                quota_notice_reason = "Google API Key not configured"
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
                        full_response += chunk
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

            messages.append({"role": "assistant", "content": full_response})

            extra_data = call.extra_data or {}
            extra_data["messages"] = messages
            extra_data["template_code"] = context["template_code"]
            extra_data["llm_provider"] = context["llm_provider"]
            extra_data["llm_model"] = context["llm_model"]
            if quota_notice_reason:
                extra_data["llm_quota_notice"] = {
                    "reason": quota_notice_reason,
                    "timestamp": now_tokyo_naive().isoformat(),
                }
            else:
                extra_data.pop("llm_quota_notice", None)

            transcript_update = call.transcript or ""
            transcript_update += (
                f"\n\n用户: {request.message}\n助手: {full_response}"
                if transcript_update
                else f"用户: {request.message}\n助手: {full_response}"
            )

            call.extra_data = extra_data
            call.transcript = transcript_update

            await self.db.commit()

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
            messages = extra_data.get("messages", [])

            if not messages:
                raise ValueError("No conversation found in call")

            template_code = request.template_code or extra_data.get("template_code", "general_appointment")
            template = await self._resolve_template(template_code)

            llm_provider = extra_data.get("llm_provider", "gemini")
            llm_model = extra_data.get("llm_model", settings.default_llm_model)

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

            appt_time = self._parse_appointment_time(extraction_result.appointment_time)

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
                category=extraction_result.category,
                summary=extraction_result.summary or extraction_result.appointment_content or "提取的预约信息",
                operation="create",
                prompt_id=template.id if template else None,
                type_name=template.category if template else "general",
                extracted_data=extraction_result.raw_data,
                extra_data=appointment_extra_data,
                raw_messages={
                    "extraction_source": "llm_chat",
                    "template_code": template_code,
                    "confidence": extraction_result.confidence,
                    "conversation": messages,
                    "extracted_data": extraction_result.raw_data,
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
