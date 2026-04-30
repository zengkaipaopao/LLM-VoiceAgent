"""Conversation orchestration for text chat and SSE streaming."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import tiktoken

from app.core.config import settings
from app.models.call import Call
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_runtime_service import ChatRuntimeService
from app.services.llm.exceptions import LLMRateLimitError
from app.services.transcript_sanitizer import (
    find_injected_user_turn_start,
    sanitize_assistant_turn,
)

OperationFlowHandler = Callable[[Call, str], Awaitable[str | None]]

JP_OPENING_GREETING = (
    "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
)


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ConversationOrchestrator:
    """Coordinate chat turns without owning appointment-domain business logic."""

    def __init__(
        self,
        *,
        chat_runtime: ChatRuntimeService,
        operation_flow_handler: OperationFlowHandler,
    ) -> None:
        self.chat_runtime = chat_runtime
        self.operation_flow_handler = operation_flow_handler

    @staticmethod
    def extract_retry_delay_seconds(error_message: str) -> int | None:
        match = re.search(r"retry in\s+([0-9.]+)s", error_message, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return max(1, int(float(match.group(1))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def looks_like_quota_error(error_message: str) -> bool:
        lowered = error_message.lower()
        keywords = ["429", "quota", "resource_exhausted", "rate limit", "too many requests"]
        return any(keyword in lowered for keyword in keywords)

    @classmethod
    def build_quota_notice_reply(
        cls,
        error_message: str,
        *,
        api_key_missing: bool = False,
    ) -> str:
        if api_key_missing:
            return (
                "⚠️ 当前未配置 Gemini API Key，暂时无法调用真实模型。"
                "请在后端 .env 中配置可用 Key 后重试。"
            )

        retry_seconds = cls.extract_retry_delay_seconds(error_message)
        retry_text = f"建议约 {retry_seconds} 秒后重试。" if retry_seconds else "请稍后重试。"
        return (
            "⚠️ 当前 Gemini 配额不足（429 RESOURCE_EXHAUSTED），暂时无法调用真实模型。"
            f"{retry_text} 请检查 Google AI Studio 项目的配额与计费设置。"
        )

    @staticmethod
    def sanitize_assistant_response(text: str) -> str:
        return sanitize_assistant_turn(text)

    @classmethod
    def extract_leading_sentence(cls, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return ""

        first_line = normalized.splitlines()[0].strip() or normalized
        sentence_match = re.match(r"^(.+?[。！？!?])", first_line)
        if sentence_match:
            return sentence_match.group(1).strip()
        return first_line[:80].strip()

    @classmethod
    def strip_redundant_opening_greeting(
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

        candidates: list[str] = [JP_OPENING_GREETING]
        for prior in prior_assistant_messages:
            prior_clean = cls.sanitize_assistant_response(prior)
            if not prior_clean:
                continue
            first_line = prior_clean.splitlines()[0].strip()
            if first_line:
                candidates.append(first_line)
            leading_sentence = cls.extract_leading_sentence(prior_clean)
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
            trimmed = normalized[len(candidate) :].lstrip()
            trimmed = re.sub(r"^[\s、，。:：\-]+", "", trimmed).lstrip()
            return trimmed or normalized

        return normalized

    @classmethod
    def find_injected_user_turn_start(cls, text: str) -> int | None:
        return find_injected_user_turn_start(text)

    @classmethod
    def normalize_messages(cls, raw_messages: Any) -> list[dict[str, str]]:
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
                content = cls.sanitize_assistant_response(content).strip()
            if not role or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    @classmethod
    def parse_messages_from_transcript(cls, transcript: str | None) -> list[dict[str, str]]:
        """Fallback: parse transcript text into message list."""
        if not transcript:
            return []

        pattern = re.compile(r"(用户|助手):\s*(.*?)(?=\n(?:用户|助手):\s*|\Z)", flags=re.S)
        parsed: list[dict[str, str]] = []
        for speaker, content in pattern.findall(transcript):
            cleaned = content.strip()
            if speaker == "助手":
                cleaned = cls.sanitize_assistant_response(cleaned).strip()
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
    def resolve_chat_response_mode(call: Call, template: Any) -> tuple[str, dict[str, Any] | None]:
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

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a single chat request and return a response."""
        call = await self.chat_runtime.get_or_create_call(request.call_id)
        context = await self.chat_runtime.setup_chat_context(request, call)

        template = context["template"]
        llm_service = context["llm_service"]
        messages = context["messages"]
        system_prompt = context["system_prompt"]
        prior_assistant_messages = self._collect_prior_assistant_messages(messages)

        messages.append({"role": "user", "content": request.message})

        temperature = self._resolve_temperature(request, template)
        resp_format, out_schema = self.resolve_chat_response_mode(call, template)
        quota_notice_reason: str | None = None

        operation_flow_response = await self.operation_flow_handler(call, request.message)
        if operation_flow_response is not None:
            response = operation_flow_response
        elif not settings.google_genai_backend_enabled:
            if not settings.llm_show_quota_notice_as_reply:
                raise ValueError("Gemini backend not configured. Please check backend/.env")
            response = self.build_quota_notice_reply(
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
                response = self.build_quota_notice_reply(quota_notice_reason)
            except Exception as llm_error:
                if not settings.llm_show_quota_notice_as_reply or not self.looks_like_quota_error(
                    str(llm_error)
                ):
                    raise
                quota_notice_reason = str(llm_error)
                response = self.build_quota_notice_reply(quota_notice_reason)

        response = self._prepare_assistant_response(response, prior_assistant_messages)
        messages.append({"role": "assistant", "content": response})
        await self.chat_runtime.persist_turn(
            call=call,
            user_message=request.message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=quota_notice_reason,
        )

        total_tokens = self._count_turn_tokens(
            user_message=request.message,
            assistant_message=response,
            system_prompt=system_prompt,
            messages=messages,
        )
        return ChatResponse(response=response, call_id=call.id, tokens_used=total_tokens)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Process a chat request and stream the response via SSE."""
        try:
            call = await self.chat_runtime.get_or_create_call(request.call_id)

            if not request.call_id:
                yield self._sse(
                    {
                        "type": "call_id",
                        "call_id": str(call.id),
                    }
                )

            context = await self.chat_runtime.setup_chat_context(request, call)
            template = context["template"]
            llm_service = context["llm_service"]
            messages = context["messages"]
            system_prompt = context["system_prompt"]
            prior_assistant_messages = self._collect_prior_assistant_messages(messages)

            messages.append({"role": "user", "content": request.message})

            temperature = self._resolve_temperature(request, template)
            resp_format, out_schema = self.resolve_chat_response_mode(call, template)

            full_response = ""
            quota_notice_reason: str | None = None

            operation_flow_response = await self.operation_flow_handler(call, request.message)
            if operation_flow_response is not None:
                full_response = operation_flow_response
                yield self._sse({"type": "content", "content": full_response})
            elif not settings.google_genai_backend_enabled:
                if not settings.llm_show_quota_notice_as_reply:
                    raise ValueError("Gemini backend not configured. Please check backend/.env")
                quota_notice_reason = "Gemini backend not configured"
                full_response = self.build_quota_notice_reply(
                    quota_notice_reason,
                    api_key_missing=True,
                )
                yield self._sse({"type": "content", "content": full_response})
            else:
                try:
                    async for chunk in llm_service.chat_stream(
                        messages=messages,
                        temperature=temperature,
                        response_format=resp_format,
                        output_schema=out_schema,
                    ):
                        candidate_response = f"{full_response}{chunk}"
                        injected_turn_start = self.find_injected_user_turn_start(
                            candidate_response
                        )

                        if injected_turn_start is not None:
                            safe_response = candidate_response[:injected_turn_start]
                            safe_delta = safe_response[len(full_response) :]
                            full_response = safe_response
                            if safe_delta:
                                yield self._sse(
                                    {
                                        "type": "content",
                                        "content": safe_delta,
                                    }
                                )
                            break

                        full_response = candidate_response
                        yield self._sse({"type": "content", "content": chunk})
                except LLMRateLimitError as rate_limit_error:
                    if not settings.llm_show_quota_notice_as_reply:
                        raise
                    quota_notice_reason = str(rate_limit_error)
                    notice = self.build_quota_notice_reply(quota_notice_reason)
                    full_response = f"{full_response}\n\n{notice}" if full_response else notice
                    yield self._sse({"type": "content", "content": notice})
                except Exception as llm_error:
                    if not settings.llm_show_quota_notice_as_reply or not self.looks_like_quota_error(
                        str(llm_error)
                    ):
                        raise
                    quota_notice_reason = str(llm_error)
                    notice = self.build_quota_notice_reply(quota_notice_reason)
                    full_response = f"{full_response}\n\n{notice}" if full_response else notice
                    yield self._sse({"type": "content", "content": notice})

            full_response = self._prepare_assistant_response(
                full_response,
                prior_assistant_messages,
            )
            messages.append({"role": "assistant", "content": full_response})
            await self.chat_runtime.persist_turn(
                call=call,
                user_message=request.message,
                assistant_message=full_response,
                context=context,
                messages=messages,
                quota_notice_reason=quota_notice_reason,
                refresh_call=False,
            )

            total_tokens = self._count_turn_tokens(
                user_message=request.message,
                assistant_message=full_response,
                system_prompt=system_prompt,
                messages=messages,
            )

            yield self._sse(
                {
                    "type": "done",
                    "call_id": str(call.id),
                    "tokens_used": total_tokens,
                }
            )

        except ValueError as value_error:
            yield self._sse({"type": "error", "error": str(value_error)})
        except Exception as exc:
            yield self._sse({"type": "error", "error": str(exc)})

    @staticmethod
    def _resolve_temperature(request: ChatRequest, template: Any) -> float:
        if request.temperature is not None:
            return request.temperature
        return getattr(template, "temperature", None) or 0.7

    @staticmethod
    def _collect_prior_assistant_messages(messages: list[dict[str, str]]) -> list[str]:
        return [
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") == "assistant" and str(item.get("content", "")).strip()
        ]

    @classmethod
    def _prepare_assistant_response(
        cls,
        response: str,
        prior_assistant_messages: list[str],
    ) -> str:
        response = cls.sanitize_assistant_response(response)
        return cls.strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )

    @staticmethod
    def _count_turn_tokens(
        *,
        user_message: str,
        assistant_message: str,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> int:
        input_text = user_message + (system_prompt if len(messages) <= 2 else "")
        input_text += json.dumps(messages)
        return count_tokens(input_text) + count_tokens(assistant_message)

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"
