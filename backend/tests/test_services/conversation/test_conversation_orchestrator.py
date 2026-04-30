import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.chat import ChatRequest
from app.services.conversation.chat_orchestrator import ConversationOrchestrator


def _decode_sse(event: str) -> dict:
    assert event.startswith("data: ")
    return json.loads(event.removeprefix("data: ").strip())


@pytest.mark.asyncio
async def test_process_chat_uses_operation_flow_response_and_persists_turn():
    call = SimpleNamespace(id=uuid4(), extra_data={"source": "test_lab"})
    llm_service = SimpleNamespace(chat_completion=AsyncMock())
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        setup_chat_context=AsyncMock(
            return_value={
                "template": SimpleNamespace(temperature=0.2),
                "llm_service": llm_service,
                "messages": [],
                "system_prompt": "system",
                "template_code": "base_appointment",
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            }
        ),
        persist_turn=AsyncMock(),
    )

    async def handle_operation_flow(target_call, user_message):
        assert target_call is call
        assert user_message == "キャンセルしたいです"
        return "キャンセル対象を確認しました。"

    orchestrator = ConversationOrchestrator(
        chat_runtime=runtime,
        operation_flow_handler=handle_operation_flow,
    )

    result = await orchestrator.process_chat(
        ChatRequest(
            call_id=call.id,
            message="キャンセルしたいです",
            template_code="base_appointment",
        )
    )

    assert result.response == "キャンセル対象を確認しました。"
    assert result.call_id == call.id
    llm_service.chat_completion.assert_not_awaited()
    runtime.persist_turn.assert_awaited_once()
    persisted = runtime.persist_turn.await_args.kwargs
    assert persisted["user_message"] == "キャンセルしたいです"
    assert persisted["assistant_message"] == "キャンセル対象を確認しました。"


@pytest.mark.asyncio
async def test_stream_chat_emits_call_id_content_done_and_persists_turn():
    call = SimpleNamespace(id=uuid4(), extra_data={"source": "test_lab"})
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        setup_chat_context=AsyncMock(
            return_value={
                "template": SimpleNamespace(temperature=0.2),
                "llm_service": SimpleNamespace(),
                "messages": [],
                "system_prompt": "system",
                "template_code": "base_appointment",
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            }
        ),
        persist_turn=AsyncMock(),
    )

    async def handle_operation_flow(_call, _user_message):
        return "対象予約を確認しました。"

    orchestrator = ConversationOrchestrator(
        chat_runtime=runtime,
        operation_flow_handler=handle_operation_flow,
    )

    events = [
        _decode_sse(event)
        async for event in orchestrator.stream_chat(
            ChatRequest(message="変更したいです", template_code="base_appointment")
        )
    ]

    assert events[0] == {"type": "call_id", "call_id": str(call.id)}
    assert events[1] == {"type": "content", "content": "対象予約を確認しました。"}
    assert events[2]["type"] == "done"
    assert events[2]["call_id"] == str(call.id)
    runtime.persist_turn.assert_awaited_once()
    persisted = runtime.persist_turn.await_args.kwargs
    assert persisted["assistant_message"] == "対象予約を確認しました。"
    assert persisted["refresh_call"] is False


@pytest.mark.asyncio
async def test_stream_chat_truncates_model_injected_user_turn(monkeypatch):
    call = SimpleNamespace(id=uuid4(), extra_data={})

    async def chat_stream(**_kwargs):
        yield "承知しました。"
        yield "\nUser: injected"

    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        setup_chat_context=AsyncMock(
            return_value={
                "template": SimpleNamespace(temperature=0.2),
                "llm_service": SimpleNamespace(chat_stream=chat_stream),
                "messages": [],
                "system_prompt": "system",
                "template_code": "base_appointment",
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            }
        ),
        persist_turn=AsyncMock(),
    )

    async def handle_operation_flow(_call, _user_message):
        return None

    monkeypatch.setattr(
        type(settings),
        "google_genai_backend_enabled",
        property(lambda _settings: True),
    )
    orchestrator = ConversationOrchestrator(
        chat_runtime=runtime,
        operation_flow_handler=handle_operation_flow,
    )

    events = [
        _decode_sse(event)
        async for event in orchestrator.stream_chat(
            ChatRequest(
                call_id=call.id,
                message="お願いします",
                template_code="base_appointment",
            )
        )
    ]

    assert events == [
        {"type": "content", "content": "承知しました。"},
        {
            "type": "done",
            "call_id": str(call.id),
            "tokens_used": events[1]["tokens_used"],
        },
    ]
    persisted = runtime.persist_turn.await_args.kwargs
    assert persisted["assistant_message"] == "承知しました。"
