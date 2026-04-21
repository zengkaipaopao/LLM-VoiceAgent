from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions import BusinessException
from app.services.twilio_voice_agent_service import TwilioVoiceAgentService


@pytest.mark.asyncio
async def test_ensure_session_requires_default_prompt_code_when_prompt_not_provided(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio_voice_agent_service.settings",
        SimpleNamespace(
            twilio_default_prompt_code="",
            default_llm_model="gemini-2.5-flash",
            openai_api_key="",
        ),
    )

    service = TwilioVoiceAgentService()

    with pytest.raises(BusinessException, match="TWILIO_DEFAULT_PROMPT_CODE is not configured"):
        await service.ensure_session(
            db=SimpleNamespace(),
            call_sid="CA123",
            prompt_code=None,
        )


@pytest.mark.asyncio
async def test_ensure_session_rejects_missing_or_inactive_prompt_template(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio_voice_agent_service.settings",
        SimpleNamespace(
            twilio_default_prompt_code="base_appointment",
            default_llm_model="gemini-2.5-flash",
            openai_api_key="",
        ),
    )
    monkeypatch.setattr(
        "app.services.twilio_voice_agent_service.resolve_prompt_runtime",
        AsyncMock(
            return_value=SimpleNamespace(
                template=None,
                template_code="base_appointment",
                system_instruction=None,
                llm_provider="gemini",
                llm_model="gemini-2.5-flash",
                temperature=0.7,
                max_tokens=512,
            )
        ),
    )

    service = TwilioVoiceAgentService()

    with pytest.raises(BusinessException, match="not found or inactive"):
        await service.ensure_session(
            db=SimpleNamespace(),
            call_sid="CA124",
            prompt_code="base_appointment",
        )

