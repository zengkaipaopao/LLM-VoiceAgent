from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock
from uuid import uuid4

import pytest

from app.schemas.chat import ChatRequest
from app.services.chat_runtime_service import ChatRuntimeService
from app.services.prompt_runtime_resolver import PromptRuntimeConfig


@pytest.mark.asyncio
async def test_get_or_create_call_fetches_existing_call():
    existing_call = SimpleNamespace(id=uuid4())
    call_repo = SimpleNamespace(get=AsyncMock(return_value=existing_call), create=AsyncMock())
    service = ChatRuntimeService(AsyncMock(), call_repo=call_repo)

    result = await service.get_or_create_call(existing_call.id)

    assert result is existing_call
    call_repo.get.assert_awaited_once_with(existing_call.id)
    call_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_call_creates_new_call_without_call_id():
    created_call = SimpleNamespace(id=uuid4())
    call_repo = SimpleNamespace(get=AsyncMock(), create=AsyncMock(return_value=created_call))
    service = ChatRuntimeService(AsyncMock(), call_repo=call_repo)

    result = await service.get_or_create_call()

    assert result is created_call
    call_repo.get.assert_not_called()
    call_repo.create.assert_awaited_once_with(
        {
            "direction": "inbound",
            "counterpart": "chat_user",
            "status": "ongoing",
            "handler_type": "ai",
        }
    )


@pytest.mark.asyncio
async def test_setup_chat_context_prefers_call_bound_runtime_and_messages(monkeypatch):
    llm_service = object()
    template = SimpleNamespace(temperature=0.4)
    runtime = PromptRuntimeConfig(
        template=template,
        template_code="base_appointment",
        template_name="Base Appointment",
        system_instruction="rendered prompt",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
        notice="loaded",
    )
    resolve_prompt_runtime = AsyncMock(return_value=runtime)
    llm_create = Mock(return_value=llm_service)

    monkeypatch.setattr(
        "app.services.chat_runtime_service.resolve_prompt_runtime",
        resolve_prompt_runtime,
    )
    monkeypatch.setattr(
        "app.services.chat_runtime_service.LLMFactory.create",
        llm_create,
    )

    raw_messages = [{"role": "assistant", "content": "Assistant: こんにちは"}]
    call = SimpleNamespace(
        extra_data={
            "template_code": "base_appointment",
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
            "messages": raw_messages,
        }
    )
    request = ChatRequest(message="hello", template_code="general_appointment")
    normalize_messages = lambda raw: [{"role": "assistant", "content": "こんにちは"}] if raw == raw_messages else []
    service = ChatRuntimeService(
        AsyncMock(),
        call_repo=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
        normalize_messages=normalize_messages,
    )

    context = await service.setup_chat_context(request, call)

    resolve_prompt_runtime.assert_awaited_once()
    assert resolve_prompt_runtime.await_args.kwargs == {
        "template_code": "base_appointment",
        "default_code": "base_appointment",
        "render_system_instruction": True,
        "model_capability": "generate",
    }
    llm_create.assert_called_once_with(
        provider="openai",
        api_key=ANY,
        model="gpt-4.1-mini",
    )
    assert context["template"] is template
    assert context["llm_service"] is llm_service
    assert context["messages"] == [{"role": "assistant", "content": "こんにちは"}]
    assert context["system_prompt"] == "rendered prompt"
    assert context["template_code"] == "base_appointment"
    assert context["llm_provider"] == "openai"
    assert context["llm_model"] == "gpt-4.1-mini"


@pytest.mark.asyncio
async def test_setup_chat_context_rejects_live_only_model_for_text_runtime(monkeypatch):
    llm_service = object()
    runtime = PromptRuntimeConfig(
        template=SimpleNamespace(temperature=0.4),
        template_code="base_appointment",
        template_name="Base Appointment",
        system_instruction="rendered prompt",
        llm_provider="gemini",
        llm_model="gemini-3.1-flash-live-preview",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
        notice="loaded",
    )
    resolve_prompt_runtime = AsyncMock(return_value=runtime)
    llm_create = Mock(return_value=llm_service)

    monkeypatch.setattr(
        "app.services.chat_runtime_service.resolve_prompt_runtime",
        resolve_prompt_runtime,
    )
    monkeypatch.setattr(
        "app.services.chat_runtime_service.LLMFactory.create",
        llm_create,
    )

    call = SimpleNamespace(extra_data={"template_code": "base_appointment", "messages": []})
    request = ChatRequest(message="hello", template_code="base_appointment")
    service = ChatRuntimeService(
        AsyncMock(),
        call_repo=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
        normalize_messages=lambda raw: [],
    )

    with pytest.raises(ValueError, match="live-only model"):
        await service.setup_chat_context(request, call)

    llm_create.assert_not_called()


@pytest.mark.asyncio
async def test_persist_turn_updates_call_metadata_and_transcript():
    db = AsyncMock()
    service = ChatRuntimeService(db, normalize_messages=lambda raw: list(raw))
    call = SimpleNamespace(
        extra_data={"llm_quota_notice": {"reason": "stale"}},
        transcript="用户: 旧消息\n助手: 旧回复",
    )
    context = {
        "template_code": "base_appointment",
        "llm_provider": "gemini",
        "llm_model": "gemini-2.5-flash",
    }
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "新消息"},
        {"role": "assistant", "content": "新回复"},
    ]

    await service.persist_turn(
        call=call,
        user_message="新消息",
        assistant_message="新回复",
        context=context,
        messages=messages,
        quota_notice_reason=None,
    )

    assert call.extra_data["messages"] == messages
    assert call.extra_data["template_code"] == "base_appointment"
    assert call.extra_data["llm_provider"] == "gemini"
    assert call.extra_data["llm_model"] == "gemini-2.5-flash"
    assert "llm_quota_notice" not in call.extra_data
    assert call.transcript.endswith("用户: 新消息\n助手: 新回复")
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(call)
