from unittest.mock import AsyncMock

import pytest

from app.services.prompt_runtime_resolver import PromptRuntimeConfig
from app.services.twilio.incoming_service import (
    TwilioAgentTurnPayload,
    TwilioIncomingService,
    TwilioIncomingVoicePayload,
)


class FakeRequest:
    def url_for(self, name: str) -> str:
        return f"https://example.test/{name}"


@pytest.mark.asyncio
async def test_incoming_non_agent_routes_to_browser_client(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.incoming_service.resolve_twilio_incoming_prompt_code",
        AsyncMock(return_value="base_appointment"),
    )

    xml = await TwilioIncomingService().build_incoming_voice_response(
        request=FakeRequest(),
        db=None,
        payload=TwilioIncomingVoicePayload(
            identity="browser-tester",
            mode="client",
            to_number="+815017930830",
        ),
    )

    assert "<Identity>browser-tester</Identity>" in xml
    assert 'name="prompt_code" value="base_appointment"' in xml


@pytest.mark.asyncio
async def test_incoming_invalid_route_returns_hangup(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.incoming_service.resolve_twilio_incoming_prompt_code",
        AsyncMock(return_value=None),
    )

    xml = await TwilioIncomingService().build_incoming_voice_response(
        request=FakeRequest(),
        db=None,
        payload=TwilioIncomingVoicePayload(
            identity="browser-tester",
            voice_route="not-a-route",
            voice_engine="not-an-engine",
            to_number="+815017930830",
        ),
    )

    assert "<Hangup/>" in xml
    assert "音声エンジン設定が不正です" in xml


@pytest.mark.asyncio
async def test_gather_agent_uses_prompt_opening_sentence(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.incoming_service.resolve_twilio_incoming_prompt_code",
        AsyncMock(return_value="base_appointment"),
    )
    monkeypatch.setattr(
        "app.services.twilio.incoming_service._resolve_prompt_runtime",
        AsyncMock(
            return_value=PromptRuntimeConfig(
                template=object(),
                template_code="base_appointment",
                template_name="Base Appointment",
                system_instruction=(
                    "セッション内で最初のアシスタント発話は必ず次の一文から開始する："
                    "「いつもお世話になっております。テストAIです。」"
                ),
                llm_provider="gemini",
                llm_model="gemini-2.5-flash",
                temperature=0.2,
                max_tokens=512,
                voice_provider=None,
                voice_id=None,
                notice=None,
            )
        ),
    )

    xml = await TwilioIncomingService().build_incoming_voice_response(
        request=FakeRequest(),
        db=None,
        payload=TwilioIncomingVoicePayload(
            identity="browser-tester",
            voice_route="gather",
            to_number="+815017930830",
        ),
    )

    assert "いつもお世話になっております。テストAIです。" in xml
    assert "prompt_code=base_appointment" in xml


@pytest.mark.asyncio
async def test_agent_turn_without_speech_returns_retry_gather():
    xml = await TwilioIncomingService().build_agent_turn_response(
        request=FakeRequest(),
        db=None,
        payload=TwilioAgentTurnPayload(
            prompt_code="base_appointment",
            call_sid="CA123",
            speech_result="",
        ),
    )

    assert "<Gather" in xml
    assert "もう一度お願いいたします" in xml
    assert "prompt_code=base_appointment" in xml
