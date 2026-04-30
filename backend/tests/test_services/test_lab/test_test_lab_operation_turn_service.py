from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.test_lab.operation_turn_service import TestSessionOperationTurnService


@pytest.mark.asyncio
async def test_operation_turn_service_persists_handled_turn():
    call_id = uuid4()
    call = SimpleNamespace(id=call_id, extra_data={}, transcript="")
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        persist_turn=AsyncMock(),
    )

    async def handle_operation_flow(target_call, user_message):
        assert target_call is call
        assert user_message == "この予約をキャンセルしてください"
        target_call.extra_data = {
            "appointment_operation_flow": {
                "status": "await_target_confirmation",
                "operation": "cancel",
            }
        }
        return "キャンセル対象を確認しました。"

    service = TestSessionOperationTurnService(
        chat_runtime=runtime,
        operation_flow_handler=handle_operation_flow,
        flow_key="appointment_operation_flow",
        normalize_messages=lambda raw: raw if isinstance(raw, list) else [],
        parse_messages_from_transcript=lambda _value: [],
        sanitize_assistant_response=lambda value: value,
        strip_redundant_opening_greeting=lambda value, **_kwargs: value,
    )

    result = await service.process(
        call_id=call_id,
        message="この予約をキャンセルしてください",
        template_code="base_appointment",
    )

    assert result.handled is True
    assert result.response == "キャンセル対象を確認しました。"
    assert result.operation == "cancel"
    assert result.state_status == "await_target_confirmation"
    runtime.persist_turn.assert_awaited_once()
    persisted = runtime.persist_turn.await_args.kwargs
    assert persisted["user_message"] == "この予約をキャンセルしてください"
    assert persisted["assistant_message"] == "キャンセル対象を確認しました。"


@pytest.mark.asyncio
async def test_operation_turn_service_skips_persist_when_not_handled():
    call_id = uuid4()
    call = SimpleNamespace(id=call_id, extra_data={}, transcript="")
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        persist_turn=AsyncMock(),
    )

    service = TestSessionOperationTurnService(
        chat_runtime=runtime,
        operation_flow_handler=AsyncMock(return_value=None),
        flow_key="appointment_operation_flow",
        normalize_messages=lambda raw: raw if isinstance(raw, list) else [],
        parse_messages_from_transcript=lambda _value: [],
        sanitize_assistant_response=lambda value: value,
        strip_redundant_opening_greeting=lambda value, **_kwargs: value,
    )

    result = await service.process(
        call_id=call_id,
        message="新規予約をしたいです",
        template_code="base_appointment",
    )

    assert result.handled is False
    assert result.response is None
    assert result.executed is False
    runtime.persist_turn.assert_not_awaited()
