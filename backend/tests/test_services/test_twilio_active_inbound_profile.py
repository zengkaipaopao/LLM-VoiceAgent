import pytest

from app.services.twilio.active_inbound_profile import (
    _get_active_inbound_profile_for_number,
    _set_active_inbound_profile_for_number,
)


@pytest.mark.asyncio
async def test_active_inbound_profile_round_trip_by_number():
    profile = await _set_active_inbound_profile_for_number(
        number="+815017930830",
        prompt_code="base_appointment",
        voice_route="official_conversational_agents",
        voice_engine="gemini",
        voice_name="Aoede",
    )

    assert profile is not None
    assert profile["prompt_code"] == "base_appointment"
    assert profile["voice_route"] == "official_conversational_agents"
    assert profile["voice_engine"] == "gemini"
    assert profile["voice_name"] == "Aoede"

    loaded = await _get_active_inbound_profile_for_number("+815017930830")

    assert loaded == profile


@pytest.mark.asyncio
async def test_active_inbound_profile_rejects_empty_payload():
    profile = await _set_active_inbound_profile_for_number(
        number="+815017930830",
        prompt_code=None,
        voice_route=None,
        voice_engine=None,
        voice_name=None,
    )

    assert profile is None
