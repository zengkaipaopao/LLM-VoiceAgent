from unittest.mock import AsyncMock

import pytest

from app.services.twilio.management_service import (
    TwilioManagementService,
    TwilioPrepareIncomingOverrideError,
    TwilioPrepareIncomingOverridePayload,
)


@pytest.mark.asyncio
async def test_prepare_incoming_voice_override_normalizes_values(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.management_service._set_pending_inbound_override_for_number",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.services.twilio.management_service._set_active_inbound_profile_for_number",
        AsyncMock(return_value={"prompt_code": "base_appointment"}),
    )

    result = await TwilioManagementService().prepare_incoming_voice_override(
        TwilioPrepareIncomingOverridePayload(
            to_number=" +81 5017930830 ",
            prompt_code="base_appointment",
            voice_route="media_stream",
            voice_engine="gemini_live",
            voice_name="Aoede",
        )
    )

    assert result["to_number"] == "+815017930830"
    assert result["prompt_code"] == "base_appointment"
    assert result["voice_route"] == "media_stream_live"
    assert result["voice_engine"] == "gemini"
    assert result["voice_name"] == "Aoede"
    assert result["shared_with_direct_inbound"] is True


@pytest.mark.asyncio
async def test_prepare_incoming_voice_override_rejects_invalid_number():
    with pytest.raises(TwilioPrepareIncomingOverrideError):
        await TwilioManagementService().prepare_incoming_voice_override(
            TwilioPrepareIncomingOverridePayload(to_number="not-a-number", voice_engine="gemini")
        )


@pytest.mark.asyncio
async def test_prepare_incoming_voice_override_requires_at_least_one_override(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.management_service._set_pending_inbound_override_for_number",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.twilio.management_service._set_active_inbound_profile_for_number",
        AsyncMock(return_value=None),
    )

    with pytest.raises(TwilioPrepareIncomingOverrideError):
        await TwilioManagementService().prepare_incoming_voice_override(
            TwilioPrepareIncomingOverridePayload(to_number="+815017930830")
        )
