"""Operation-turn handling for Test Lab chat sessions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from app.models.call import Call
from app.schemas.chat import TestSessionOperationTurnResponse
from app.services.chat_runtime_service import ChatRuntimeService

OperationFlowHandler = Callable[[Call, str], Awaitable[str | None]]
NormalizeMessagesFn = Callable[[Any], list[dict[str, str]]]
ParseTranscriptFn = Callable[[str | None], list[dict[str, str]]]
SanitizeAssistantFn = Callable[[str], str]
StripOpeningFn = Callable[..., str]


class TestSessionOperationTurnService:
    """Advance a Test Lab session through appointment operation flow only."""
    __test__ = False

    def __init__(
        self,
        *,
        chat_runtime: ChatRuntimeService,
        operation_flow_handler: OperationFlowHandler,
        flow_key: str,
        normalize_messages: NormalizeMessagesFn,
        parse_messages_from_transcript: ParseTranscriptFn,
        sanitize_assistant_response: SanitizeAssistantFn,
        strip_redundant_opening_greeting: StripOpeningFn,
    ) -> None:
        self.chat_runtime = chat_runtime
        self.operation_flow_handler = operation_flow_handler
        self.flow_key = flow_key
        self.normalize_messages = normalize_messages
        self.parse_messages_from_transcript = parse_messages_from_transcript
        self.sanitize_assistant_response = sanitize_assistant_response
        self.strip_redundant_opening_greeting = strip_redundant_opening_greeting

    async def process(
        self,
        *,
        call_id: UUID,
        message: str,
        template_code: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> TestSessionOperationTurnResponse:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message cannot be empty")

        call = await self.chat_runtime.get_or_create_call(call_id)
        extra_data = dict(call.extra_data or {})
        messages = self.normalize_messages(extra_data.get("messages"))
        if not messages:
            messages = self.parse_messages_from_transcript(call.transcript)
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

        response = await self.operation_flow_handler(call, normalized_message)
        if response is None:
            flow = dict((call.extra_data or {}).get(self.flow_key) or {})
            return TestSessionOperationTurnResponse(
                call_id=call.id,
                handled=False,
                operation=str(flow.get("operation") or "") or None,
                state_status=str(flow.get("status") or "") or None,
                executed=isinstance((call.extra_data or {}).get("operation_execution"), dict),
            )

        response = self.sanitize_assistant_response(response)
        response = self.strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )

        messages.append({"role": "user", "content": normalized_message})
        messages.append({"role": "assistant", "content": response})
        await self.chat_runtime.persist_turn(
            call=call,
            user_message=normalized_message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=None,
        )

        refreshed_extra_data = dict(call.extra_data or {})
        flow = dict(refreshed_extra_data.get(self.flow_key) or {})
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
