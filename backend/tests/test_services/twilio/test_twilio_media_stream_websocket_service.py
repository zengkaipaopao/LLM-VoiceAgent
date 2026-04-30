from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.prompt_runtime_resolver import PromptRuntimeConfig
from app.services.twilio.media_stream_bootstrap import TwilioMediaStreamBootstrap
from app.services.twilio.media_stream_websocket_service import TwilioMediaStreamWebSocketService


class FakeWebSocket:
    def __init__(self) -> None:
        self.closed: tuple[int | None, str | None] | None = None

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closed = (code, reason)


@pytest.mark.asyncio
async def test_media_stream_websocket_service_builds_bridge_context(monkeypatch):
    bootstrap = TwilioMediaStreamBootstrap(
        initial_payload={},
        stream_sid="MZ123",
        call_sid="CA123",
        prompt_code="base_appointment",
        voice_route="official_demo_live",
        voice_name="Aoede",
        from_number="+811",
        to_number="+812",
        custom_parameters={},
    )
    runtime = PromptRuntimeConfig(
        template=None,
        template_code="official_demo_baseline",
        template_name="Official Demo Baseline",
        system_instruction="hello",
        llm_provider="gemini",
        llm_model="gemini-live-2.5-flash-native-audio",
        temperature=0.2,
        max_tokens=512,
        voice_provider="gemini",
        voice_id="Aoede",
        notice="loaded",
    )
    bridge_runtime = SimpleNamespace(legacy_manual_vad=False)
    run_bridge = AsyncMock()

    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.receive_twilio_media_stream_start",
        AsyncMock(return_value=bootstrap),
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.build_official_demo_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._resolve_gemini_live_model",
        lambda _model: "gemini-live-2.5-flash-native-audio",
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.resolve_live_provider",
        lambda _provider, _model: "gemini",
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.provider_available",
        lambda _provider: (True, None),
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._validate_twilio_activity_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._validate_twilio_media_stream_bridge_profile",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._resolve_media_stream_bridge_profile",
        lambda: "cx_agent_studio",
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._use_manual_vad_control",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.build_twilio_media_stream_runtime_config",
        lambda **_kwargs: bridge_runtime,
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service._build_gemini_live_config",
        lambda **_kwargs: {"live": True},
    )
    monkeypatch.setattr(
        "app.services.twilio.media_stream_websocket_service.run_twilio_media_stream_bridge",
        run_bridge,
    )

    await TwilioMediaStreamWebSocketService().run(
        websocket=FakeWebSocket(),
        prompt_code="base_appointment",
        voice_name=None,
    )

    run_bridge.assert_awaited_once()
    context = run_bridge.await_args.args[0]
    assert context.current_call_sid == "CA123"
    assert context.stream_sid == "MZ123"
    assert context.selected_provider == "gemini"
    assert context.selected_voice == "Aoede"
