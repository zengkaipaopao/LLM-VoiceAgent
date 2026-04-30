import pytest

from app.services.live_gateway.browser_realtime import (
    build_browser_live_connect_config,
    build_live_config,
    decode_audio_chunk,
    encode_audio_chunk,
    normalize_modalities_for_model,
    parse_modalities,
)


def test_parse_modalities_filters_invalid_values_and_deduplicates():
    assert parse_modalities(None) == ["AUDIO"]
    assert parse_modalities("audio,text,audio,unknown") == ["AUDIO", "TEXT"]
    assert parse_modalities("unknown") == ["AUDIO"]


def test_normalize_modalities_for_preview_model_forces_audio_only():
    modalities, notice = normalize_modalities_for_model(
        "gemini-3.1-flash-live-preview",
        ["AUDIO", "TEXT"],
    )

    assert modalities == ["AUDIO"]
    assert notice is not None


def test_encode_decode_audio_chunk_roundtrip():
    encoded = encode_audio_chunk(b"abc")

    assert encoded == "YWJj"
    assert decode_audio_chunk(encoded) == b"abc"
    assert encode_audio_chunk("already-encoded") == "already-encoded"
    assert encode_audio_chunk(None) is None


def test_decode_audio_chunk_rejects_invalid_base64():
    with pytest.raises(Exception):
        decode_audio_chunk("not base64!!")


def test_build_live_config_enables_browser_activity_detection():
    config = build_live_config(
        modalities=["AUDIO"],
        voice_name="Aoede",
        system_instruction="hello",
    )

    assert config.realtime_input_config is not None
    activity_detection = config.realtime_input_config.automatic_activity_detection
    assert activity_detection is not None
    assert activity_detection.disabled is False
    assert activity_detection.silence_duration_ms == 200
    assert config.speech_config is not None


def test_build_browser_live_connect_config_keeps_auth_token_constraints_simple():
    config = build_browser_live_connect_config(
        modalities=["TEXT"],
        voice_name="Aoede",
        system_instruction="hello",
    )

    assert config.response_modalities == ["TEXT"]
    assert config.realtime_input_config is None
    assert config.speech_config is None
