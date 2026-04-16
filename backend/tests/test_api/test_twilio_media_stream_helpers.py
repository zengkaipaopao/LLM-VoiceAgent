import json
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.api.v1.endpoints.twilio import (
    _build_gemini_live_config,
    _build_twilio_media_stream_twiml,
    _candidate_websocket_signature_urls,
    _consume_pending_inbound_override_for_number,
    _extract_stream_custom_parameters,
    _extract_twilio_google_voice_names,
    _extract_twilio_tts_voice_ids,
    _is_auto_closing_reply,
    _resolve_gemini_live_model,
    _resolve_twilio_inbound_voice_route,
    _set_pending_inbound_override_for_number,
    _use_manual_vad_control,
)
from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.media_stream_state import TwilioMediaStreamState
from app.services.twilio.normalizers import _normalize_gemini_live_voice_name


class _FakeWebSocket:
    def __init__(self, messages: list[str]):
        self._messages = list(messages)
        self.closed = False

    async def receive_text(self) -> str:
        if not self._messages:
            raise WebSocketDisconnect()
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True


def test_build_twilio_media_stream_twiml_uses_custom_parameters_instead_of_query_string():
    request = SimpleNamespace(
        url_for=lambda name: (
            "https://example.com/api/v1/twilio/voice/stream/status"
            if name == "twilio_voice_stream_status_callback"
            else "https://example.com/api/v1/twilio/voice/stream"
        )
    )

    xml = _build_twilio_media_stream_twiml(
        request=request,
        prompt_code="base_appointment",
        from_number="+819012345678",
        to_number="+13185551234",
        voice_name="Aoede",
    )

    assert 'url="wss://example.com/api/v1/twilio/voice/stream"' in xml
    assert 'statusCallback="https://example.com/api/v1/twilio/voice/stream/status"' in xml
    assert 'statusCallbackMethod="POST"' in xml
    assert "prompt_code=base_appointment" not in xml
    assert '<Parameter name="prompt_code" value="base_appointment" />' in xml
    assert '<Parameter name="from" value="+819012345678" />' in xml
    assert '<Parameter name="to" value="+13185551234" />' in xml
    assert '<Parameter name="voice_name" value="Aoede" />' in xml


def test_build_twilio_media_stream_twiml_can_preplay_opening_greeting():
    request = SimpleNamespace(
        url_for=lambda name: (
            "https://example.com/api/v1/twilio/voice/stream/status"
            if name == "twilio_voice_stream_status_callback"
            else "https://example.com/api/v1/twilio/voice/stream"
        )
    )

    xml = _build_twilio_media_stream_twiml(
        request=request,
        prompt_code="base_appointment",
        from_number="+819012345678",
        to_number="+13185551234",
        voice_name="Aoede",
        opening_text="いつもお世話になっております。",
    )

    assert '<Say language="ja-JP">いつもお世話になっております。</Say>' in xml
    assert xml.index("<Say") < xml.index("<Connect>")


def test_candidate_websocket_signature_urls_prefers_wss_and_trailing_slash():
    websocket = SimpleNamespace(
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "example.ngrok-free.app",
        },
        url=SimpleNamespace(
            scheme="ws",
            netloc="localhost:8000",
            path="/api/v1/twilio/voice/stream",
            query="",
        ),
    )

    candidates = _candidate_websocket_signature_urls(websocket)

    assert candidates[0] == "wss://example.ngrok-free.app/api/v1/twilio/voice/stream"
    assert "wss://example.ngrok-free.app/api/v1/twilio/voice/stream/" in candidates
    assert "https://example.ngrok-free.app/api/v1/twilio/voice/stream" in candidates


def test_extract_twilio_google_voice_names_filters_google_chirp3_hd_for_language():
    markdown = """
***
Language (Locale): Japanese (Japan)
Language code: ja-JP
Type: Generative
Provider: Google
Voice: ja-JP-Chirp3-HD-Aoede
***
Language (Locale): Japanese (Japan)
Language code: ja-JP
Type: Generative
Provider: Google
Voice: ja-JP-Chirp3-HD-Orus
***
Language (Locale): Japanese (Japan)
Language code: ja-JP
Type: Standard
Provider: Google
Voice: ja-JP-Standard-B
***
Language (Locale): English (US)
Language code: en-US
Type: Generative
Provider: Google
Voice: en-US-Chirp3-HD-Aoede
"""

    assert _extract_twilio_google_voice_names(markdown, language_code="ja-JP") == ["Aoede", "Orus"]


def test_extract_twilio_tts_voice_ids_supports_amazon_and_google():
    markdown = """
***
Language code: ja-JP
Provider: Google
Voice: ja-JP-Chirp3-HD-Aoede
***
Language code: ja-JP
Provider: Amazon
Voice: Mizuki
***
Language code: ja-JP
Provider: Amazon
Voice: Takumi
"""

    assert _extract_twilio_tts_voice_ids(markdown, language_code="ja-JP", provider="Google") == [
        "ja-JP-Chirp3-HD-Aoede"
    ]
    assert _extract_twilio_tts_voice_ids(markdown, language_code="ja-JP", provider="Amazon") == [
        "Mizuki",
        "Takumi",
    ]


def test_build_gemini_live_config_disables_thinking_for_manual_twilio_without_explicit_vad_flag():
    config = _build_gemini_live_config(
        model="gemini-2.5-flash-native-audio-latest",
        system_instruction="hello",
        voice_name="Aoede",
        manual_vad=True,
    )

    assert config.realtime_input_config.automatic_activity_detection.disabled is True
    assert getattr(config, "explicit_vad_signal", None) is None
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
    assert config.thinking_config.include_thoughts is False


def test_build_gemini_live_config_applies_explicit_auto_vad_settings(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.live_config.settings",
        SimpleNamespace(
            twilio_gemini_activity_mode="auto",
            twilio_gemini_activity_handling="no_interruption",
            twilio_gemini_turn_coverage="activity_only",
            twilio_gemini_start_sensitivity="high",
            twilio_gemini_end_sensitivity="high",
            twilio_gemini_prefix_padding_ms=120,
            twilio_gemini_silence_duration_ms=450,
            twilio_agent_language="ja-JP",
        ),
    )

    config = _build_gemini_live_config(
        model="gemini-live-2.5-flash-native-audio",
        system_instruction="hello",
        voice_name="Aoede",
        manual_vad=False,
    )

    aad = config.realtime_input_config.automatic_activity_detection
    assert aad.disabled is False
    assert str(config.realtime_input_config.activity_handling.value) == "NO_INTERRUPTION"
    assert str(config.realtime_input_config.turn_coverage.value) == "TURN_INCLUDES_ONLY_ACTIVITY"
    assert str(aad.start_of_speech_sensitivity.value) == "START_SENSITIVITY_HIGH"
    assert str(aad.end_of_speech_sensitivity.value) == "END_SENSITIVITY_HIGH"
    assert aad.prefix_padding_ms == 120
    assert aad.silence_duration_ms == 450
    assert config.speech_config.language_code == "ja-JP"
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Aoede"


def test_normalize_gemini_live_voice_name_accepts_short_and_twilio_google_names():
    assert _normalize_gemini_live_voice_name("Aoede") == "Aoede"
    assert _normalize_gemini_live_voice_name("ja-JP-Chirp3-HD-Aoede") == "Aoede"
    assert _normalize_gemini_live_voice_name("Google.Aoede") == "Aoede"


def test_normalize_gemini_live_voice_name_falls_back_for_non_gemini_voices():
    assert (
        _normalize_gemini_live_voice_name(
            "3JDquces8E8bkmvbh6Bc",
            default_voice="Aoede",
        )
        == "Aoede"
    )
    assert (
        _normalize_gemini_live_voice_name(
            "Mizuki",
            voice_provider="amazon",
            default_voice="Aoede",
        )
        == "Aoede"
    )


def test_extract_stream_custom_parameters_reads_start_payload():
    payload = {
        "event": "start",
        "start": {
            "callSid": "CA123",
            "customParameters": {
                "prompt_code": "base_appointment",
                "from": "+819012345678",
            },
        },
    }

    params = _extract_stream_custom_parameters(payload)

    assert params == {
        "prompt_code": "base_appointment",
        "from": "+819012345678",
    }


@pytest.mark.asyncio
async def test_receive_twilio_media_stream_start_ignores_noise_and_extracts_custom_parameters():
    websocket = _FakeWebSocket(
        [
            json.dumps({"event": "connected"}),
            json.dumps({"event": "mark", "mark": {"name": "noop"}}),
            json.dumps(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ123",
                        "callSid": "CA123",
                        "customParameters": {
                            "prompt_code": "base_appointment",
                            "voice_name": "ja-JP-Chirp3-HD-Aoede",
                            "from": "+819012345678",
                            "to": "+13185551234",
                        },
                    },
                }
            ),
        ]
    )

    bootstrap = await receive_twilio_media_stream_start(
        websocket,
        prompt_code=None,
        voice_name=None,
    )

    assert bootstrap is not None
    assert bootstrap.stream_sid == "MZ123"
    assert bootstrap.call_sid == "CA123"
    assert bootstrap.prompt_code == "base_appointment"
    assert bootstrap.voice_name == "ja-JP-Chirp3-HD-Aoede"
    assert bootstrap.from_number == "+819012345678"
    assert bootstrap.to_number == "+13185551234"


@pytest.mark.asyncio
async def test_receive_twilio_media_stream_start_closes_on_stop_event():
    websocket = _FakeWebSocket([json.dumps({"event": "stop"})])

    bootstrap = await receive_twilio_media_stream_start(
        websocket,
        prompt_code="fallback_prompt",
        voice_name="Aoede",
    )

    assert bootstrap is None
    assert websocket.closed is True


def test_media_stream_state_tracks_playback_and_waiting_flags():
    state = TwilioMediaStreamState(
        pre_roll_frame_limit=4,
        adaptive_threshold_floor=55,
    )

    state.start_waiting_for_model(now=12.5, manual_turn=True)
    state.mark_model_audio_sent()
    mark_name = state.next_playback_mark()

    assert state.awaiting_model_response is True
    assert state.awaiting_manual_turn is True
    assert state.model_turn_sent_audio is True
    assert state.assistant_playback_pending is True
    assert mark_name == "assistant-turn-1"

    assert state.confirm_playback_mark("assistant-turn-0") is False
    assert state.confirm_playback_mark(mark_name) is True
    assert state.assistant_playback_pending is False

    state.finalize_turn_playback_state(now=13.0)
    assert state.awaiting_model_response is False
    assert state.model_turn_sent_audio is False


def test_media_stream_state_interrupt_clears_runtime_locks():
    state = TwilioMediaStreamState(
        pre_roll_frame_limit=4,
        adaptive_threshold_floor=55,
    )
    state.assistant_speaking = True
    state.pending_playback_mark = "assistant-turn-3"
    state.assistant_playback_pending = True
    state.begin_opening_suppression(now=20.0, duration_ms=2000)
    state.start_waiting_for_model(now=20.0, manual_turn=False)

    state.interrupt(now=21.0)

    assert state.assistant_speaking is False
    assert state.pending_playback_mark is None
    assert state.assistant_playback_pending is False
    assert state.awaiting_model_response is False
    assert state.opening_suppress_until is None
    assert state.assistant_last_output_at == 21.0


def test_is_auto_closing_reply_requires_closing_tokens_and_non_question_suffix():
    assert _is_auto_closing_reply("依頼内容を承りました。ご利用ありがとうございます。")
    assert _is_auto_closing_reply("承知いたしました。ご利用ありがとうございます。")
    assert not _is_auto_closing_reply("ご利用ありがとうございます。続けて住所を教えてください。")
    assert not _is_auto_closing_reply("承りましたが、この内容でよろしいですか？")


@pytest.mark.asyncio
async def test_pending_inbound_override_can_be_prepared_and_consumed():
    queued = await _set_pending_inbound_override_for_number(
        number="+815012345678",
        prompt_code="base_appointment",
        voice_route=None,
        voice_engine="gemini",
        voice_name="Aoede",
    )

    assert queued is True

    payload = await _consume_pending_inbound_override_for_number("+815012345678")
    assert payload == {
        "prompt_code": "base_appointment",
        "voice_engine": "gemini",
        "voice_name": "Aoede",
    }

    assert await _consume_pending_inbound_override_for_number("+815012345678") is None


@pytest.mark.asyncio
async def test_pending_inbound_override_can_store_voice_route():
    queued = await _set_pending_inbound_override_for_number(
        number="+815012345679",
        prompt_code="base_appointment",
        voice_route="media_stream_live",
        voice_engine=None,
        voice_name="Aoede",
    )

    assert queued is True

    payload = await _consume_pending_inbound_override_for_number("+815012345679")
    assert payload == {
        "prompt_code": "base_appointment",
        "voice_route": "media_stream_live",
        "voice_engine": None,
        "voice_name": "Aoede",
    }


def test_resolve_twilio_inbound_voice_route_prefers_explicit_route():
    assert (
        _resolve_twilio_inbound_voice_route(
            voice_route="media_stream_live",
            voice_engine="twilio",
        )
        == "media_stream_live"
    )


def test_resolve_twilio_inbound_voice_route_maps_legacy_engine_values():
    assert _resolve_twilio_inbound_voice_route(voice_route=None, voice_engine="twilio") == "gather"
    assert (
        _resolve_twilio_inbound_voice_route(voice_route=None, voice_engine="gemini")
        == "media_stream_live"
    )


def test_twilio_defaults_to_auto_vad_control(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.live_config.settings",
        SimpleNamespace(twilio_gemini_activity_mode="auto"),
    )
    assert _use_manual_vad_control() is False


def test_twilio_manual_vad_mode_remains_available(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.live_config.settings",
        SimpleNamespace(twilio_gemini_activity_mode="manual"),
    )
    assert _use_manual_vad_control() is True


def test_resolve_gemini_live_model_maps_legacy_preview_to_vertex_native_audio(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.twilio.settings",
        SimpleNamespace(
            default_live_model="gemini-2.5-flash-native-audio-latest",
            google_vertex_enabled=True,
        ),
    )

    assert _resolve_gemini_live_model("gemini-3.1-flash-live-preview") == "gemini-live-2.5-flash-native-audio"
