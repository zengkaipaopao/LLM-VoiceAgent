from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.appointments.operation_executor import AppointmentOperationExecutor


@pytest.mark.asyncio
async def test_operation_executor_cancel_updates_target_and_creates_event():
    target_id = uuid4()
    call_id = uuid4()
    operation_event_id = uuid4()
    call = SimpleNamespace(
        id=call_id,
        caller_name="田中",
        extra_data={
            "messages": [{"role": "user", "content": "キャンセルしたいです"}],
            "appointment_operation_flow": {"status": "await_execute_confirmation"},
        },
    )
    appointment = SimpleNamespace(
        id=target_id,
        call_id=uuid4(),
        caller_name="田中",
        company="株式会社ERI",
        appointment=datetime(2026, 5, 1, 11, 0),
        category="粗大ゴミ",
        amount="3kg",
        address="神田1-2-3",
        extra_request="",
        extra_data={},
        prompt_id=uuid4(),
        type_name="waste_collection",
    )
    appointment_repo = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(id=operation_event_id))
    )
    db = SimpleNamespace(commit=AsyncMock())
    executor = AppointmentOperationExecutor(
        db,
        appointment_repo=appointment_repo,
    )

    response = await executor.execute(
        call=call,
        appointment=appointment,
        operation="cancel",
        pending_changes={},
        flow={"operation": "cancel"},
        extra_data={"source": "test_lab", "template_code": "base_appointment"},
        user_message="はい",
    )

    assert "キャンセルが完了しました。" in response
    assert appointment.extra_data["lifecycle_status"] == "cancelled"
    assert appointment.extra_data["latest_operation_type"] == "cancel"
    assert appointment.extra_data["latest_operation_event_id"] == str(operation_event_id)
    assert call.extra_data["operation_execution"] == {
        "operation": "cancel",
        "appointment_id": str(operation_event_id),
        "target_appointment_id": str(target_id),
        "confirmed_at": call.extra_data["operation_execution"]["confirmed_at"],
    }
    assert "appointment_operation_flow" not in call.extra_data

    appointment_repo.create.assert_awaited_once()
    payload = appointment_repo.create.await_args.args[0]
    assert payload["operation"] == "cancel"
    assert payload["extracted_data"]["target_appointment_id"] == str(target_id)
    assert payload["extra_data"]["target_appointment_id"] == str(target_id)
    assert payload["raw_messages"]["extraction_source"] == "operation_flow"
    db.commit.assert_awaited_once()
