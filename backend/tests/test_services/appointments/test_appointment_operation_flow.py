from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.appointments.operation_flow import AppointmentOperationFlowService


@pytest.mark.asyncio
async def test_operation_flow_enters_cancel_confirmation_for_single_candidate():
    appointment = SimpleNamespace(
        id=uuid4(),
        appointment=datetime(2026, 5, 1, 11, 0),
        caller_name="田中",
        company="株式会社ERI",
        category="粗大ゴミ",
        amount="3kg",
        address="神田1-2-3",
        extra_request="",
        extracted_data={},
    )
    call = SimpleNamespace(id=uuid4(), extra_data={})
    matcher = SimpleNamespace(
        find_candidates=AsyncMock(return_value=([appointment], {"caller_name": "田中"}))
    )
    flow = AppointmentOperationFlowService(
        appointment_repo=SimpleNamespace(),
        matcher=matcher,
        executor=SimpleNamespace(),
    )

    response = await flow.handle(call, "田中です。2026年5月1日11時の予約をキャンセルしたいです。")

    assert response is not None
    assert "キャンセルのご依頼ですね" in response
    assert str(appointment.id) in call.extra_data["appointment_operation_flow"]["candidate_ids"]
    assert call.extra_data["appointment_operation_flow"]["status"] == "await_target_confirmation"


@pytest.mark.asyncio
async def test_operation_flow_executes_cancel_after_affirmative_confirmation():
    appointment = SimpleNamespace(
        id=uuid4(),
        appointment=datetime(2026, 5, 1, 11, 0),
        caller_name="田中",
    )
    call = SimpleNamespace(
        id=uuid4(),
        extra_data={
            "appointment_operation_flow": {
                "status": "await_target_confirmation",
                "operation": "cancel",
                "candidate_ids": [str(appointment.id)],
            }
        },
    )
    executor = SimpleNamespace(execute=AsyncMock(return_value="キャンセルが完了しました。"))
    flow = AppointmentOperationFlowService(
        appointment_repo=SimpleNamespace(get=AsyncMock(return_value=appointment)),
        matcher=SimpleNamespace(),
        executor=executor,
    )

    response = await flow.handle(call, "はい")

    assert response == "キャンセルが完了しました。"
    executor.execute.assert_awaited_once()
    payload = executor.execute.await_args.kwargs
    assert payload["call"] is call
    assert payload["appointment"] is appointment
    assert payload["operation"] == "cancel"
