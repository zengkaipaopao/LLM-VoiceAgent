from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.chat import ExtractionRequest, ExtractionResponse
from app.services.extraction.appointment_application_service import (
    AppointmentExtractionApplicationService,
)
from app.services.extraction_service import AppointmentExtraction


@pytest.mark.asyncio
async def test_extraction_application_returns_existing_appointment():
    call = SimpleNamespace(id=uuid4(), extra_data={})
    appointment = SimpleNamespace(id=uuid4(), extracted_data={"already": True})
    service = AppointmentExtractionApplicationService(
        SimpleNamespace(commit=AsyncMock()),
        call_repo=SimpleNamespace(get=AsyncMock(return_value=call)),
        appointment_repo=SimpleNamespace(get_by_call_id=AsyncMock(return_value=appointment)),
        prompt_service=SimpleNamespace(),
        extraction_applier=SimpleNamespace(apply=AsyncMock()),
    )

    result = await service.extract_appointment(ExtractionRequest(call_id=call.id))

    assert result.success is True
    assert result.appointment_id == appointment.id
    assert result.extracted_data == {"already": True}


@pytest.mark.asyncio
async def test_extraction_application_returns_completed_operation_execution():
    operation_event_id = uuid4()
    call = SimpleNamespace(
        id=uuid4(),
        extra_data={
            "operation_execution": {
                "operation": "cancel",
                "appointment_id": str(operation_event_id),
            }
        },
    )
    service = AppointmentExtractionApplicationService(
        SimpleNamespace(commit=AsyncMock()),
        call_repo=SimpleNamespace(get=AsyncMock(return_value=call)),
        appointment_repo=SimpleNamespace(get_by_call_id=AsyncMock(return_value=None)),
        prompt_service=SimpleNamespace(),
        extraction_applier=SimpleNamespace(apply=AsyncMock()),
    )

    result = await service.extract_appointment(ExtractionRequest(call_id=call.id))

    assert result.success is True
    assert result.appointment_id == operation_event_id
    assert result.extracted_data["operation"] == "cancel"


@pytest.mark.asyncio
async def test_extraction_application_applies_fresh_llm_extraction(monkeypatch):
    call = SimpleNamespace(
        id=uuid4(),
        extra_data={
            "messages": [{"role": "user", "content": "粗大ゴミを予約したいです"}],
            "template_code": "base_appointment",
        },
        transcript="",
    )
    template = SimpleNamespace(id=uuid4(), category="waste")
    extraction = AppointmentExtraction(
        caller_name="田中",
        appointment_content="粗大ゴミの予約",
        summary="粗大ゴミの予約",
        confidence=0.9,
        raw_data={"request_type": "new"},
    )
    expected = ExtractionResponse(
        success=True,
        appointment_id=uuid4(),
        extracted_data=extraction.model_dump(),
        confidence=0.9,
        message="预约信息提取成功",
    )
    extraction_applier = SimpleNamespace(apply=AsyncMock(return_value=expected))

    async def resolve_runtime(*_args, **_kwargs):
        return SimpleNamespace(
            template=template,
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
        )

    class FakeExtractionService:
        def __init__(self, llm_service):
            self.llm_service = llm_service

        async def extract_appointment(self, **_kwargs):
            return extraction

    monkeypatch.setattr(
        "app.services.extraction.appointment_application_service.resolve_prompt_runtime",
        resolve_runtime,
    )
    monkeypatch.setattr(
        "app.services.extraction.appointment_application_service.LLMFactory.create",
        lambda **_kwargs: SimpleNamespace(name="llm"),
    )
    monkeypatch.setattr(
        "app.services.extraction.appointment_application_service.ExtractionService",
        FakeExtractionService,
    )

    service = AppointmentExtractionApplicationService(
        SimpleNamespace(commit=AsyncMock()),
        call_repo=SimpleNamespace(get=AsyncMock(return_value=call)),
        appointment_repo=SimpleNamespace(get_by_call_id=AsyncMock(return_value=None)),
        prompt_service=SimpleNamespace(),
        extraction_applier=extraction_applier,
    )

    result = await service.extract_appointment(ExtractionRequest(call_id=call.id))

    assert result is expected
    extraction_applier.apply.assert_awaited_once()
    kwargs = extraction_applier.apply.await_args.kwargs
    assert kwargs["call"] is call
    assert kwargs["extraction_result"] == extraction
    assert kwargs["template"] is template
    assert kwargs["template_code"] == "base_appointment"
