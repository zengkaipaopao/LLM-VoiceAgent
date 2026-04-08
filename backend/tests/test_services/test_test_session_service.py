from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.test_session_service import TestSessionService


@pytest.mark.asyncio
async def test_start_test_session_uses_prompt_runtime_and_creates_call():
    started_at = datetime(2026, 4, 8, 10, 0, 0)
    template = SimpleNamespace(
        id="prompt-id",
        code="base_appointment",
        name="Base Appointment",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
        system_prompt="system prompt",
    )
    created_call = SimpleNamespace(id=uuid4(), started_at=started_at)
    call_repo = SimpleNamespace(create=AsyncMock(return_value=created_call))
    service = TestSessionService(
        db=SimpleNamespace(),
        call_repo=call_repo,
        appointment_repo=SimpleNamespace(),
        prompt_service=SimpleNamespace(
            get_template=AsyncMock(return_value=template),
        ),
    )

    result = await service.start_test_session(
        template_code="base_appointment",
        caller_name="Caller",
    )

    assert result.call_id == created_call.id
    assert result.template_code == "base_appointment"
    assert result.llm_provider == "gemini"
    assert result.llm_model == "gemini-2.5-flash"
    assert result.started_at == started_at
    call_repo.create.assert_awaited_once()
    payload = call_repo.create.await_args.args[0]
    assert payload["prompt_id"] == "prompt-id"
    assert payload["extra_data"]["template_code"] == "base_appointment"
    assert payload["extra_data"]["llm_provider"] == "gemini"
    assert payload["extra_data"]["llm_model"] == "gemini-2.5-flash"
    assert payload["caller_name"] == "Caller"


@pytest.mark.asyncio
async def test_finalize_test_session_reuses_existing_appointment_without_reextracting():
    call_id = uuid4()
    appointment_id = uuid4()
    started_at = datetime(2026, 4, 8, 10, 0, 0)
    ended_at = datetime(2026, 4, 8, 10, 5, 0)
    call = SimpleNamespace(
        id=call_id,
        started_at=started_at,
        answered_at=started_at,
        ended_at=ended_at,
        duration_seconds=None,
        status="ongoing",
        is_answered=False,
        extra_data={"template_code": "base_appointment"},
    )
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = TestSessionService(
        db=db,
        call_repo=SimpleNamespace(get=AsyncMock(return_value=call)),
        appointment_repo=SimpleNamespace(
            get_by_call_id=AsyncMock(
                return_value=SimpleNamespace(id=appointment_id, extracted_data={"foo": "bar"})
            )
        ),
        prompt_service=SimpleNamespace(),
    )

    result = await service.finalize_test_session(call_id=call_id)

    assert result.call_id == call_id
    assert result.status == "completed"
    assert result.duration_seconds == 300
    assert result.appointment_id == appointment_id
    assert result.already_extracted is True
    assert result.extraction is not None
    assert result.extraction.extracted_data == {"foo": "bar"}
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_finalize_test_session_requires_extraction_callback_for_new_records():
    call_id = uuid4()
    started_at = datetime(2026, 4, 8, 10, 0, 0)
    ended_at = datetime(2026, 4, 8, 10, 1, 0)
    call = SimpleNamespace(
        id=call_id,
        started_at=started_at,
        answered_at=started_at,
        ended_at=ended_at,
        duration_seconds=None,
        status="ongoing",
        is_answered=False,
        extra_data={"template_code": "base_appointment"},
    )
    service = TestSessionService(
        db=SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock()),
        call_repo=SimpleNamespace(get=AsyncMock(return_value=call)),
        appointment_repo=SimpleNamespace(get_by_call_id=AsyncMock(return_value=None)),
        prompt_service=SimpleNamespace(),
    )

    with pytest.raises(RuntimeError, match="extract_appointment callback is required"):
        await service.finalize_test_session(call_id=call_id, run_extraction=True)
