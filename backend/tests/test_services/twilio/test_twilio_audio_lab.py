from __future__ import annotations

import base64
import math
import sys
from array import array

from app.services.twilio.audio_lab import (
    decode_audio_base64_payload,
    prepare_audio_lab_variants,
)


def _pcm16_bytes_from_samples(samples: list[int]) -> bytes:
    pcm = array("h", samples)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()


def _sine_wave_bytes(*, sample_rate: int, seconds: float, amplitude: int = 4000, hz: int = 440) -> bytes:
    total_samples = max(1, int(sample_rate * seconds))
    samples = [
        int(amplitude * math.sin((2.0 * math.pi * hz * index) / sample_rate))
        for index in range(total_samples)
    ]
    return _pcm16_bytes_from_samples(samples)


def test_decode_audio_base64_payload_normalizes_odd_length_bytes():
    payload = base64.b64encode(b"\x01\x02\x03").decode("ascii")

    decoded = decode_audio_base64_payload(payload)

    assert decoded == b"\x01\x02"


def test_prepare_audio_lab_variants_builds_three_preview_paths():
    audio_bytes = _sine_wave_bytes(sample_rate=16000, seconds=0.25)

    variants = prepare_audio_lab_variants(audio_bytes=audio_bytes, sample_rate=16000)

    assert [variant.variant_id for variant in variants] == [
        "original_recording",
        "twilio_preview",
        "gemini_preview",
    ]
    assert variants[0].sample_rate == 16000
    assert variants[1].sample_rate == 8000
    assert variants[2].sample_rate == 16000
    assert variants[0].pcm_bytes == audio_bytes
    assert variants[1].pcm_bytes != audio_bytes
    assert variants[2].pcm_bytes != b""
    assert variants[0].stats["duration_ms"] > 0
    assert variants[1].stats["duration_ms"] > 0
    assert variants[2].stats["duration_ms"] > 0
    assert variants[0].wav_bytes.startswith(b"RIFF")
    assert variants[1].wav_bytes.startswith(b"RIFF")
    assert variants[2].wav_bytes.startswith(b"RIFF")

