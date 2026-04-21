import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.api.v1.endpoints.twilio import (
    _build_gemini_live_config,
    _build_twilio_inbound_debug_capture,
    _build_twilio_media_stream_twiml,
    _candidate_websocket_signature_urls,
    _consume_pending_inbound_override_for_number,
    _extract_opening_sentence,
    _extract_stream_custom_parameters,
    _extract_twilio_google_voice_names,
    _extract_twilio_tts_voice_ids,
    _is_auto_closing_reply,
    _require_opening_sentence,
    _resolve_gemini_live_model,
    _resolve_twilio_inbound_voice_route,
    _set_pending_inbound_override_for_number,
    _use_manual_vad_control,
    _validate_twilio_activity_mode,
)
from app.exceptions import BusinessException
from app.services.twilio.audio_codec import (
    TwilioMediaAudioCodec,
    pcm16_bytes_to_samples,
    samples_to_ulaw_bytes,
    ulaw_bytes_to_samples,
)
from app.services.twilio.debug_audio_capture import RollingPcmCapture
from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.media_stream_state import (
    AssistantPlaybackOverlapBuffer,
    TwilioMediaStreamState,
)
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
    assert '<Parameter name="voice_route" value="media_stream_live" />' not in xml
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


def test_build_twilio_media_stream_twiml_can_embed_voice_route():
    request = SimpleNamespace(
        url_for=lambda name: (
            "https://example.com/api/v1/twilio/voice/stream/status"
            if name == "twilio_voice_stream_status_callback"
            else "https://example.com/api/v1/twilio/voice/stream"
        )
    )

    xml = _build_twilio_media_stream_twiml(
        request=request,
        prompt_code=None,
        from_number=None,
        to_number=None,
        voice_name="Aoede",
        route_name="official_demo_live",
    )

    assert '<Parameter name="voice_route" value="official_demo_live" />' in xml


def test_build_twilio_inbound_debug_capture_supports_followup_variants():
    capture = _build_twilio_inbound_debug_capture("followup_pcm8k_raw")
    assert capture.sample_rate == 8000
    assert capture.artifact_key == "followup-pcm8k-raw"

    capture = _build_twilio_inbound_debug_capture("followup_pcm16k_resampled")
    assert capture.sample_rate == 16000
    assert capture.artifact_key == "followup-pcm16k-resampled"


def test_extract_opening_sentence_prefers_explicit_first_utterance_quote():
    opening_text = _extract_opening_sentence(
        "あなたは受付AIです。最初のアシスタント発話は必ず次の一文で開始してください。"
        "「お電話ありがとうございます。本日のご用件をお聞かせください。」"
    )

    assert opening_text == "お電話ありがとうございます。本日のご用件をお聞かせください。"


def test_require_opening_sentence_raises_when_prompt_lacks_explicit_first_utterance():
    with pytest.raises(BusinessException, match="must define the first assistant utterance"):
        _require_opening_sentence(
            system_instruction="あなたは受付AIです。丁寧に会話してください。",
            template_code="base_appointment",
        )


def test_rolling_pcm_capture_can_reset_and_report_full():
    capture = RollingPcmCapture(sample_rate=4, sample_width_bytes=1, duration_seconds=1)
    capture.append(b"abcd")

    assert capture.current_bytes == 4
    assert capture.is_full is True

    capture.reset()

    assert capture.current_bytes == 0
    assert capture.is_full is False


def test_assistant_playback_overlap_buffer_only_triggers_after_sustained_hits():
    buffer = AssistantPlaybackOverlapBuffer(
        sample_rate=16000,
        max_buffer_ms=100,
        trigger_rms=120,
        min_hits=3,
    )
    frame = b"\x01\x02" * 320

    assert buffer.observe(pcm16k=frame, conditioned_rms=130) is False
    assert buffer.observe(pcm16k=frame, conditioned_rms=140) is False
    assert buffer.observe(pcm16k=frame, conditioned_rms=150) is True

    drained = buffer.drain()
    assert drained.endswith(frame)
    assert len(drained) <= buffer.max_buffer_bytes


def test_assistant_playback_overlap_buffer_resets_when_energy_drops():
    buffer = AssistantPlaybackOverlapBuffer(
        sample_rate=16000,
        max_buffer_ms=100,
        trigger_rms=120,
        min_hits=2,
    )
    frame = b"\x01\x02" * 320

    assert buffer.observe(pcm16k=frame, conditioned_rms=140) is False
    assert buffer.observe(pcm16k=frame, conditioned_rms=0) is False
    assert buffer.observe(pcm16k=frame, conditioned_rms=140) is False
    assert buffer.observe(pcm16k=frame, conditioned_rms=140) is True


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
            twilio_gemini_activity_handling="interrupt",
            twilio_gemini_turn_coverage="all_input",
            twilio_gemini_start_sensitivity="low",
            twilio_gemini_end_sensitivity="high",
            twilio_gemini_prefix_padding_ms=0,
            twilio_gemini_silence_duration_ms=200,
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
    assert config.response_modalities == ["AUDIO"]
    assert str(config.realtime_input_config.activity_handling.value) == "START_OF_ACTIVITY_INTERRUPTS"
    assert str(config.realtime_input_config.turn_coverage.value) == "TURN_INCLUDES_ALL_INPUT"
    assert str(aad.start_of_speech_sensitivity.value) == "START_SENSITIVITY_LOW"
    assert str(aad.end_of_speech_sensitivity.value) == "END_SENSITIVITY_HIGH"
    assert aad.prefix_padding_ms in (None, 0)
    assert aad.silence_duration_ms == 200
    assert config.speech_config.language_code == "ja-JP"
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Aoede"
    assert config.input_audio_transcription.language_codes == ["ja-JP"]
    assert config.output_audio_transcription.language_codes == ["ja-JP"]


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
                            "voice_route": "official_demo_live",
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
    assert bootstrap.voice_route == "official_demo_live"
    assert bootstrap.voice_name == "ja-JP-Chirp3-HD-Aoede"
    assert bootstrap.from_number == "+819012345678"
    assert bootstrap.to_number == "+13185551234"
    assert bootstrap.custom_parameters["voice_route"] == "official_demo_live"


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
    state = TwilioMediaStreamState()

    state.mark_model_audio_sent()
    mark_name = state.next_playback_mark()

    assert state.model_turn_sent_audio is True
    assert state.assistant_playback_pending is True
    assert mark_name == "assistant-turn-1"

    assert state.confirm_playback_mark("assistant-turn-0") is False
    assert state.confirm_playback_mark(mark_name) is True
    assert state.assistant_playback_pending is False

    state.finalize_turn_playback_state(now=13.0)
    assert state.model_turn_sent_audio is False


def test_media_stream_state_interrupt_clears_runtime_locks():
    state = TwilioMediaStreamState()
    state.assistant_speaking = True
    state.pending_playback_mark = "assistant-turn-3"
    state.assistant_playback_pending = True
    state.model_turn_sent_audio = True

    state.interrupt(now=21.0)

    assert state.assistant_speaking is False
    assert state.pending_playback_mark is None
    assert state.assistant_playback_pending is False
    assert state.assistant_last_output_at == 21.0
    assert state.model_turn_sent_audio is False


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
        "voice_route": "official_conversational_agents",
        "voice_engine": None,
        "voice_name": "Aoede",
    }


def test_resolve_twilio_inbound_voice_route_prefers_explicit_route():
    assert (
        _resolve_twilio_inbound_voice_route(
            voice_route="media_stream_live",
            voice_engine="twilio",
        )
        == "official_conversational_agents"
    )
    assert (
        _resolve_twilio_inbound_voice_route(
            voice_route="official_demo_live",
            voice_engine="twilio",
        )
        == "official_conversational_agents"
    )
    assert (
        _resolve_twilio_inbound_voice_route(
            voice_route="official_conversational_agents",
            voice_engine="twilio",
        )
        == "official_conversational_agents"
    )


def test_resolve_twilio_inbound_voice_route_maps_legacy_engine_values():
    assert _resolve_twilio_inbound_voice_route(voice_route=None, voice_engine="twilio") == "gather"
    assert (
        _resolve_twilio_inbound_voice_route(voice_route=None, voice_engine="gemini")
        == "official_conversational_agents"
    )


def test_twilio_defaults_to_auto_vad_control(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.live_config.settings",
        SimpleNamespace(twilio_gemini_activity_mode="auto"),
    )
    assert _use_manual_vad_control() is False
    _validate_twilio_activity_mode()


def test_twilio_manual_vad_mode_is_rejected_for_media_stream_bridge(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.live_config.settings",
        SimpleNamespace(twilio_gemini_activity_mode="manual"),
    )
    assert _use_manual_vad_control() is True
    with pytest.raises(ValueError, match="only supports Gemini automatic activity detection"):
        _validate_twilio_activity_mode()


def test_twilio_media_audio_codec_batches_twilio_frames_before_sending_upstream():
    codec = TwilioMediaAudioCodec(input_batch_ms=100, twilio_frame_bytes=160)
    twilio_payload = base64.b64encode(b"\xff" * 160).decode("ascii")

    batches: list[bytes] = []
    for _ in range(6):
        decoded = codec.decode_twilio_payload(twilio_payload)
        batches.extend(codec.queue_inbound_audio(decoded.pcm16k))

    assert len(batches) == 1
    assert len(batches[0]) == 3200
    assert codec.pending_inbound_bytes > 0


def test_ulaw_decoder_matches_g711_reference_anchor_values():
    assert ulaw_bytes_to_samples(bytes([0x00])) == [-32124]
    assert ulaw_bytes_to_samples(bytes([0x01])) == [-31100]
    assert ulaw_bytes_to_samples(bytes([0x7F])) == [0]
    assert ulaw_bytes_to_samples(bytes([0x80])) == [32124]
    assert ulaw_bytes_to_samples(bytes([0xFF])) == [0]


def test_twilio_media_audio_codec_encodes_model_audio_back_to_twilio_frames():
    codec = TwilioMediaAudioCodec(input_batch_ms=100, twilio_frame_bytes=160)
    pcm24k_silence = b"\x00\x00" * 2400

    frames = codec.encode_model_audio(
        pcm24k_silence,
        mime_type="audio/pcm;rate=24000",
    )

    assert frames
    assert all(len(frame) <= 160 for frame in frames)


def test_twilio_media_audio_codec_noise_gate_suppresses_low_rms_tail_noise():
    codec = TwilioMediaAudioCodec(
        input_batch_ms=20,
        twilio_frame_bytes=160,
        input_noise_gate_enabled=True,
        input_noise_gate_open_rms=140,
        input_noise_gate_close_rms=90,
        input_noise_gate_hold_ms=20,
    )

    quiet_payload = base64.b64encode(samples_to_ulaw_bytes([60] * 160)).decode("ascii")
    loud_payload = base64.b64encode(samples_to_ulaw_bytes([2400] * 160)).decode("ascii")

    quiet_before = codec.decode_twilio_payload(quiet_payload)
    loud = codec.decode_twilio_payload(loud_payload)
    quiet_after = codec.decode_twilio_payload(quiet_payload)
    quiet_final = codec.decode_twilio_payload(quiet_payload)

    quiet_before_samples = pcm16_bytes_to_samples(quiet_before.pcm16k)
    loud_samples = pcm16_bytes_to_samples(loud.pcm16k)
    quiet_after_samples = pcm16_bytes_to_samples(quiet_after.pcm16k)
    quiet_final_samples = pcm16_bytes_to_samples(quiet_final.pcm16k)

    assert max(abs(sample) for sample in quiet_before_samples) == 0
    assert max(abs(sample) for sample in loud_samples) > 0
    assert max(abs(sample) for sample in quiet_after_samples) > 0
    assert max(abs(sample) for sample in quiet_final_samples) <= 64


def test_resolve_gemini_live_model_maps_legacy_preview_to_vertex_native_audio(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.twilio.settings",
        SimpleNamespace(
            default_live_model="gemini-2.5-flash-native-audio-latest",
            google_vertex_enabled=True,
        ),
    )

    assert _resolve_gemini_live_model("gemini-3.1-flash-live-preview") == "gemini-live-2.5-flash-native-audio"
