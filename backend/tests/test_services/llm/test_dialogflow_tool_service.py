from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.schemas.dialogflow import DialogflowCreateAppointmentToolRequest
from app.services.dialogflow_tool_service import DialogflowToolService


def _build_request(**overrides) -> DialogflowCreateAppointmentToolRequest:
    payload = {
        "request_type": "new",
        "appointment_datetime": datetime.fromisoformat("2026-04-29T12:00:00+09:00"),
        "pickup_address": "神田1-2-3",
        "waste_items": "粗大ゴミ",
        "amount": "2トン",
        "company_name": "株式会社EII",
        "contact_name": "Zeng",
        "extra_request": "特になし",
        "user_confirmed": True,
    }
    payload.update(overrides)
    return DialogflowCreateAppointmentToolRequest(**payload)


def test_build_summary_includes_core_fields():
    payload = _build_request()

    summary = DialogflowToolService.build_summary(payload)

    assert "2026-04-29 12:00" in summary
    assert "神田1-2-3" in summary
    assert "粗大ゴミ" in summary
    assert "2トン" in summary
    assert "株式会社EII" in summary
    assert "Zeng" in summary


@pytest.mark.asyncio
async def test_create_new_appointment_requires_confirmation():
    payload = _build_request(user_confirmed=False)

    service = DialogflowToolService(db=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="user_confirmed must be true"):
        await service.create_new_appointment(payload)


@pytest.mark.asyncio
async def test_resolve_prompt_id_defaults_to_base_appointment(monkeypatch: pytest.MonkeyPatch):
    expected_id = UUID("11111111-1111-1111-1111-111111111111")

    async def fake_get_template(self, code: str):
        assert code == "base_appointment"
        return SimpleNamespace(id=expected_id)

    monkeypatch.setattr("app.services.prompt_service.PromptService.get_template", fake_get_template)

    service = DialogflowToolService(db=object())  # type: ignore[arg-type]
    payload = _build_request()

    prompt_id = await service.resolve_prompt_id(payload)

    assert prompt_id == expected_id
