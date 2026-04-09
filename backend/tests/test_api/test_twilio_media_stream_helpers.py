import pytest
from types import SimpleNamespace

from app.api.v1.endpoints.twilio import (
    _build_twilio_conversation_relay_twiml,
    _build_gemini_live_config,
    _candidate_websocket_signature_urls,
    _build_twilio_media_stream_twiml,
    _consume_pending_inbound_override_for_number,
    _extract_twilio_conversationrelay_default_voice_settings,
    _extract_twilio_tts_voice_ids,
    _extract_twilio_google_voice_names,
    _extract_stream_custom_parameters,
    _is_auto_closing_reply,
    _normalize_twilio_conversationrelay_voice_id,
    _normalize_twilio_google_voice_id,
    _resolve_twilio_conversationrelay_default_voice,
    _set_pending_inbound_override_for_number,
    _use_manual_vad_control,
)


def test_build_twilio_media_stream_twiml_uses_custom_parameters_instead_of_query_string():
    request = SimpleNamespace(
        url_for=lambda _: "https://example.com/api/v1/twilio/voice/stream"
    )

    xml = _build_twilio_media_stream_twiml(
        request=request,
        prompt_code="base_appointment",
        from_number="+819012345678",
        to_number="+13185551234",
        voice_name="Aoede",
    )

    assert 'url="wss://example.com/api/v1/twilio/voice/stream"' in xml
    assert "prompt_code=base_appointment" not in xml
    assert '<Parameter name="prompt_code" value="base_appointment" />' in xml
    assert '<Parameter name="from" value="+819012345678" />' in xml
    assert '<Parameter name="to" value="+13185551234" />' in xml
    assert '<Parameter name="voice_name" value="Aoede" />' in xml


def test_build_twilio_media_stream_twiml_can_preplay_opening_greeting():
    request = SimpleNamespace(
        url_for=lambda _: "https://example.com/api/v1/twilio/voice/stream"
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


def test_build_twilio_conversation_relay_twiml_uses_conversationrelay_with_custom_parameters():
    request = SimpleNamespace(
        url_for=lambda name: (
            "https://example.com/api/v1/twilio/voice/status"
            if name == "voice_status_callback"
            else "https://example.com/api/v1/twilio/voice/conversationrelay"
        )
    )

    xml = _build_twilio_conversation_relay_twiml(
        request=request,
        prompt_code="base_appointment",
        from_number="+819012345678",
        to_number="+13185551234",
        tts_provider="Google",
        voice_name="Aoede",
        opening_text="いつもお世話になっております。",
    )

    assert '<Connect action="https://example.com/api/v1/twilio/voice/status">' in xml
    assert 'url="wss://example.com/api/v1/twilio/voice/conversationrelay"' in xml
    assert 'welcomeGreeting="いつもお世話になっております。"' in xml
    assert 'welcomeGreetingInterruptible="none"' in xml
    assert 'ttsProvider="Google"' in xml
    assert 'transcriptionProvider="Google"' in xml
    assert 'speechModel="telephony"' in xml
    assert 'interruptible="speech"' in xml
    assert 'reportInputDuringAgentSpeech=' not in xml
    assert 'interruptSensitivity="high"' in xml
    assert 'ttsProvider="Google"' in xml
    assert 'voice="Aoede"' in xml
    assert '<Parameter name="prompt_code" value="base_appointment" />' in xml
    assert '<Parameter name="from" value="+819012345678" />' in xml
    assert '<Parameter name="to" value="+13185551234" />' in xml
    assert '<Parameter name="tts_provider" value="Google" />' in xml


def test_build_twilio_conversation_relay_twiml_supports_elevenlabs_provider():
    request = SimpleNamespace(
        url_for=lambda name: (
            "https://example.com/api/v1/twilio/voice/status"
            if name == "voice_status_callback"
            else "https://example.com/api/v1/twilio/voice/conversationrelay"
        )
    )

    xml = _build_twilio_conversation_relay_twiml(
        request=request,
        prompt_code="base_appointment",
        from_number="+819012345678",
        to_number="+13185551234",
        tts_provider="ElevenLabs",
        voice_name="3JDquces8E8bkmvbh6Bc",
        opening_text="こんにちは。",
    )

    assert 'ttsProvider="ElevenLabs"' in xml
    assert 'voice="3JDquces8E8bkmvbh6Bc"' in xml
    assert '<Parameter name="tts_provider" value="ElevenLabs" />' in xml


def test_candidate_websocket_signature_urls_prefers_wss_and_trailing_slash():
    websocket = SimpleNamespace(
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "example.ngrok-free.app",
        },
        url=SimpleNamespace(
            scheme="ws",
            netloc="localhost:8000",
            path="/api/v1/twilio/voice/conversationrelay",
            query="",
        ),
    )

    candidates = _candidate_websocket_signature_urls(websocket)

    assert candidates[0] == "wss://example.ngrok-free.app/api/v1/twilio/voice/conversationrelay"
    assert "wss://example.ngrok-free.app/api/v1/twilio/voice/conversationrelay/" in candidates
    assert "https://example.ngrok-free.app/api/v1/twilio/voice/conversationrelay" in candidates


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


def test_extract_twilio_conversationrelay_default_voice_settings_parses_markdown_table():
    markdown = """
| Language | Voice ID             | TTS provider | Speech model | Transcription provider |
| -------- | -------------------- | ------------ | ------------ | ---------------------- |
| ja-JP    | 3JDquces8E8bkmvbh6Bc | ElevenLabs   | telephony    | Google                 |
| en-US    | UgBBYS2sOqTuMpoF3BR0 | ElevenLabs   | telephony    | Google                 |
"""

    parsed = _extract_twilio_conversationrelay_default_voice_settings(markdown)

    assert parsed["ja-JP"]["voice_id"] == "3JDquces8E8bkmvbh6Bc"
    assert parsed["ja-JP"]["tts_provider"] == "ElevenLabs"


def test_normalize_twilio_google_voice_id_accepts_short_and_full_names():
    assert _normalize_twilio_google_voice_id("Aoede", language_code="ja-JP") == "ja-JP-Chirp3-HD-Aoede"
    assert (
        _normalize_twilio_google_voice_id("ja-JP-Chirp3-HD-Orus", language_code="ja-JP")
        == "ja-JP-Chirp3-HD-Orus"
    )


def test_normalize_twilio_conversationrelay_voice_id_supports_google_short_names_and_elevenlabs_format():
    assert (
        _normalize_twilio_conversationrelay_voice_id(
            "Aoede",
            tts_provider="Google",
            language_code="ja-JP",
            supported_voices=["ja-JP-Chirp3-HD-Aoede", "ja-JP-Chirp3-HD-Orus"],
            default_voice="ja-JP-Chirp3-HD-Aoede",
        )
        == "ja-JP-Chirp3-HD-Aoede"
    )
    assert (
        _normalize_twilio_conversationrelay_voice_id(
            "3JDquces8E8bkmvbh6Bc-turbo_v2_5-0.8_0.8_0.6",
            tts_provider="ElevenLabs",
            language_code="ja-JP",
            supported_voices=["3JDquces8E8bkmvbh6Bc"],
            default_voice="3JDquces8E8bkmvbh6Bc",
        )
        == "3JDquces8E8bkmvbh6Bc-turbo_v2_5-0.8_0.8_0.6"
    )


def test_resolve_twilio_conversationrelay_default_voice_prefers_configured_default(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.twilio.settings",
        SimpleNamespace(twilio_default_conversationrelay_voice="jqcCZkN6Knx8BJ5TBdYR"),
    )

    assert (
        _resolve_twilio_conversationrelay_default_voice(
            tts_provider="ElevenLabs",
            language_code="ja-JP",
            supported_voices=["3JDquces8E8bkmvbh6Bc"],
            default_voice="3JDquces8E8bkmvbh6Bc",
        )
        == "jqcCZkN6Knx8BJ5TBdYR"
    )


def test_build_gemini_live_config_disables_thinking_and_enables_explicit_vad_for_manual_twilio():
    config = _build_gemini_live_config(
        model="gemini-2.5-flash-native-audio-latest",
        system_instruction="hello",
        voice_name="Aoede",
        manual_vad=True,
    )

    assert config.explicit_vad_signal is True
    assert config.realtime_input_config.automatic_activity_detection.disabled is True
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
    assert config.thinking_config.include_thoughts is False


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
        voice_engine="gemini",
        tts_provider="Google",
        voice_name="Aoede",
    )

    assert queued is True

    payload = await _consume_pending_inbound_override_for_number("+815012345678")
    assert payload == {
        "prompt_code": "base_appointment",
        "voice_engine": "gemini",
        "tts_provider": "Google",
        "voice_name": "Aoede",
    }

    assert await _consume_pending_inbound_override_for_number("+815012345678") is None


def test_twilio_defaults_to_manual_vad_control():
    assert _use_manual_vad_control() is True
