from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.appointments.extraction_applier import AppointmentExtractionApplier
from app.services.extraction_service import AppointmentExtraction


@pytest.mark.asyncio
async def test_try_apply_operation_request_executes_cancel_and_returns_operation_event():
    target = SimpleNamespace(id=uuid4())
    operation_event_id = uuid4()
    call = SimpleNamespace(id=uuid4(), extra_data={})
    db = SimpleNamespace(commit=AsyncMock())
    matcher = SimpleNamespace(
        resolve_extracted_operation_target=AsyncMock(return_value=target)
    )

    async def execute_operation(**kwargs):
        kwargs["call"].extra_data = {
            **kwargs["extra_data"],
            "operation_execution": {
                "operation": kwargs["operation"],
                "appointment_id": str(operation_event_id),
                "target_appointment_id": str(target.id),
            },
        }

    executor = SimpleNamespace(execute=AsyncMock(side_effect=execute_operation))
    applier = AppointmentExtractionApplier(
        db,
        appointment_repo=SimpleNamespace(),
        matcher=matcher,
        executor=executor,
    )

    result = await applier.try_apply_operation_request(
        call=call,
        raw_data={
            "request_type": "cancel",
            "caller_name": "田中",
            "original_appointment_time": "2026-05-01T11:00:00+09:00",
        },
        extraction_summary="田中様からの2026年5月1日11時の予約キャンセル依頼。",
        extraction_confidence=1.0,
        extra_data={"source": "test_lab"},
    )

    assert result is not None
    assert result.success is True
    assert result.appointment_id == operation_event_id
    assert result.extracted_data["operation"] == "cancel"
    assert result.extracted_data["target_appointment_id"] == str(target.id)
    matcher.resolve_extracted_operation_target.assert_awaited_once_with(
        call=call,
        raw_data={
            "request_type": "cancel",
            "caller_name": "田中",
            "original_appointment_time": "2026-05-01T11:00:00+09:00",
        },
    )
    executor.execute.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_persists_new_appointment_when_no_operation_request():
    appointment_id = uuid4()
    call = SimpleNamespace(
        id=uuid4(),
        caller_name="Fallback Caller",
        transcript="用户: 粗大ゴミ3kgの予約をしたいです。",
    )
    appointment_repo = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(id=appointment_id))
    )
    applier = AppointmentExtractionApplier(
        SimpleNamespace(commit=AsyncMock()),
        appointment_repo=appointment_repo,
        matcher=SimpleNamespace(resolve_extracted_operation_target=AsyncMock()),
        executor=SimpleNamespace(execute=AsyncMock()),
    )

    result = await applier.apply(
        call=call,
        extraction_result=AppointmentExtraction(
            caller_name="田中",
            company="株式会社IAI",
            appointment_time="2026-05-01T11:00:00+09:00",
            appointment_content="粗大ゴミ3kgの回収予約",
            category="粗大ゴミ",
            summary="田中様からの粗大ゴミ3kgの回収予約。",
            confidence=0.92,
            raw_data={
                "request_type": "new",
                "estimated_weight_kg": 3,
                "address": "品川区1-2-3",
                "extra_request": "時間厳守",
            },
        ),
        messages=[{"role": "user", "content": "粗大ゴミ3kgの予約をしたいです。"}],
        template=SimpleNamespace(id=uuid4(), category="waste"),
        template_code="base_appointment",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        extra_data={"source": "test_lab", "simulation": True},
    )

    assert result.success is True
    assert result.appointment_id == appointment_id
    payload = appointment_repo.create.await_args.args[0]
    assert payload["call_id"] == call.id
    assert payload["caller_name"] == "田中"
    assert payload["company"] == "株式会社IAI"
    assert payload["appointment"] == datetime(2026, 5, 1, 11, 0)
    assert payload["category"] == "粗大ゴミ"
    assert payload["amount"] == "3 kg"
    assert payload["address"] == "品川区1-2-3"
    assert payload["extra_request"] == "備考: 時間厳守"
    assert payload["operation"] == "create"
    assert payload["extra_data"]["source"] == "test_lab"
    assert payload["extra_data"]["simulation"] is True
