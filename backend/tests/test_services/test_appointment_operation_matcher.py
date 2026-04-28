from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.appointments.operation_matcher import AppointmentOperationMatcher


@pytest.mark.asyncio
async def test_operation_matcher_does_not_scan_without_identity_hints():
    repo = SimpleNamespace(search_operation_candidates_with_call=AsyncMock(return_value=[]))
    matcher = AppointmentOperationMatcher(repo)

    candidates, hints = await matcher.find_candidates(
        SimpleNamespace(caller_name="Test Caller", counterpart="chat_user"),
        "こないだの予定を変更したいです",
    )

    assert candidates == []
    assert hints == {}
    repo.search_operation_candidates_with_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_operation_matcher_resolves_extracted_cancel_by_name_and_time():
    target = SimpleNamespace(
        id=uuid4(),
        call_id=uuid4(),
        caller_name="田中",
        company="株式会社IAI",
        appointment=datetime(2026, 5, 1, 11, 0),
        timestamp=datetime(2026, 4, 27, 10, 2),
        address="品川区1-2-3",
        extra_data={},
    )
    repo = SimpleNamespace(
        get=AsyncMock(return_value=None),
        search_operation_candidates_with_call=AsyncMock(
            return_value=[
                (target, SimpleNamespace(counterpart="+817000000000", caller_name="田中"))
            ]
        ),
    )
    matcher = AppointmentOperationMatcher(repo)

    resolved = await matcher.resolve_extracted_operation_target(
        call=SimpleNamespace(id=uuid4()),
        raw_data={
            "request_type": "cancel",
            "caller_name": "田中",
            "company": None,
            "original_appointment_time": "2026-05-01T11:00:00+09:00",
        },
    )

    assert resolved == target
    repo.search_operation_candidates_with_call.assert_awaited_once()
