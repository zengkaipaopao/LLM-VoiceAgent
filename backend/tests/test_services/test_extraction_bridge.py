from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.extraction_bridge import ExtractionBridgeService


@pytest.mark.asyncio
async def test_resolve_finalized_call_reuses_operation_execution_result():
    appointment_id = uuid4()
    appointment_repo = SimpleNamespace(get_by_call_id=AsyncMock())
    extract_appointment = AsyncMock()
    service = ExtractionBridgeService(
        appointment_repo=appointment_repo,
        extract_appointment=extract_appointment,
    )
    call = SimpleNamespace(
        id=uuid4(),
        extra_data={
            "template_code": "base_appointment",
            "operation_execution": {
                "operation": "update",
                "appointment_id": str(appointment_id),
                "changes": {"appointment": "2026-04-10T10:00:00"},
            },
        },
    )

    resolved_id, extraction_result, already_extracted = await service.resolve_finalized_call(call=call)

    assert resolved_id == appointment_id
    assert extraction_result is not None
    assert extraction_result.appointment_id == appointment_id
    assert extraction_result.extracted_data["operation"] == "update"
    assert already_extracted is True
    appointment_repo.get_by_call_id.assert_not_called()
    extract_appointment.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_finalized_call_reuses_existing_appointment_before_reextracting():
    appointment_id = uuid4()
    appointment_repo = SimpleNamespace(
        get_by_call_id=AsyncMock(
            return_value=SimpleNamespace(id=appointment_id, extracted_data={"foo": "bar"})
        )
    )
    extract_appointment = AsyncMock()
    service = ExtractionBridgeService(
        appointment_repo=appointment_repo,
        extract_appointment=extract_appointment,
    )
    call = SimpleNamespace(id=uuid4(), extra_data={"template_code": "base_appointment"})

    resolved_id, extraction_result, already_extracted = await service.resolve_finalized_call(call=call)

    assert resolved_id == appointment_id
    assert extraction_result is not None
    assert extraction_result.extracted_data == {"foo": "bar"}
    assert already_extracted is True
    appointment_repo.get_by_call_id.assert_awaited_once_with(call.id)
    extract_appointment.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_finalized_call_runs_extraction_for_new_records():
    appointment_id = uuid4()
    extract_appointment = AsyncMock(
        return_value=SimpleNamespace(
            appointment_id=appointment_id,
            success=True,
            extracted_data={"category": "粗大ゴミ"},
            confidence=0.9,
            message="ok",
        )
    )
    service = ExtractionBridgeService(
        appointment_repo=SimpleNamespace(get_by_call_id=AsyncMock(return_value=None)),
        extract_appointment=extract_appointment,
    )
    call = SimpleNamespace(id=uuid4(), extra_data={"template_code": "base_appointment"})

    resolved_id, extraction_result, already_extracted = await service.resolve_finalized_call(
        call=call,
        template_code="override_template",
    )

    assert resolved_id == appointment_id
    assert extraction_result is not None
    assert extraction_result.appointment_id == appointment_id
    assert already_extracted is False
    extract_appointment.assert_awaited_once()
    request = extract_appointment.await_args.args[0]
    assert request.call_id == call.id
    assert request.template_code == "override_template"
