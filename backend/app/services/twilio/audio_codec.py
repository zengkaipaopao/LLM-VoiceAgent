from __future__ import annotations

import base64
import math
import re
import sys
from array import array
from dataclasses import dataclass, field
from typing import Iterable, Sequence

_AUDIO_RATE_PATTERN = re.compile(r"rate=(\d+)")
_TWILIO_INPUT_SAMPLE_RATE = 8000
_GEMINI_INPUT_SAMPLE_RATE = 16000
_TWILIO_OUTPUT_SAMPLE_RATE = 8000
_DEFAULT_MODEL_OUTPUT_SAMPLE_RATE = 24000
_PCM16_MAX = 32767
_PCM16_MIN = -32768
_ULAW_BIAS = 0x84
_ULAW_CLIP = 32635
_ULAW_SEG_UEND = (0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF, 0x7FFF)
_ULAW_DECODE_TABLE = tuple(
    (
        (_ULAW_BIAS - (((((~code) & 0x0F) << 3) + _ULAW_BIAS) << (((~code) & 0x70) >> 4)))
        if ((~code) & 0x80)
        else (((((~code) & 0x0F) << 3) + _ULAW_BIAS) << (((~code) & 0x70) >> 4)) - _ULAW_BIAS
    )
    for code in range(256)
)


def _extract_audio_rate(mime_type: str | None, default: int = _DEFAULT_MODEL_OUTPUT_SAMPLE_RATE) -> int:
    text = (mime_type or "").strip().lower()
    if not text:
        return default
    matched = _AUDIO_RATE_PATTERN.search(text)
    if not matched:
        return default
    try:
        return int(matched.group(1))
    except ValueError:
        return default


def _chunk_bytes(buffer: bytes, chunk_size: int) -> list[bytes]:
    if not buffer or chunk_size <= 0:
        return []
    return [buffer[index : index + chunk_size] for index in range(0, len(buffer), chunk_size)]


def _clamp_pcm16(sample: float) -> int:
    return max(_PCM16_MIN, min(_PCM16_MAX, int(round(sample))))


def _samples_to_pcm16_bytes(samples: Iterable[int]) -> bytes:
    pcm = array("h", (_clamp_pcm16(sample) for sample in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()


def pcm16_bytes_to_samples(audio_bytes: bytes) -> list[int]:
    aligned = audio_bytes if len(audio_bytes) % 2 == 0 else audio_bytes[:-1]
    if not aligned:
        return []
    pcm = array("h")
    pcm.frombytes(aligned)
    if sys.byteorder != "little":
        pcm.byteswap()
    return list(pcm)


def _ulaw_byte_to_sample(code: int) -> int:
    return _ULAW_DECODE_TABLE[code & 0xFF]


def ulaw_bytes_to_samples(ulaw_bytes: bytes) -> list[int]:
    return [_ulaw_byte_to_sample(code) for code in ulaw_bytes]


def _sample_to_ulaw(sample: int) -> int:
    pcm = max(_PCM16_MIN, min(_PCM16_MAX, int(sample)))
    sign = 0x80 if pcm < 0 else 0x00
    if pcm < 0:
        pcm = -pcm
    if pcm > _ULAW_CLIP:
        pcm = _ULAW_CLIP
    pcm += _ULAW_BIAS

    exponent = 7
    for index, boundary in enumerate(_ULAW_SEG_UEND):
        if pcm <= boundary:
            exponent = index
            break
    mantissa = (pcm >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def samples_to_ulaw_bytes(samples: Iterable[int]) -> bytes:
    return bytes(_sample_to_ulaw(sample) for sample in samples)


def compute_pcm16_stats(samples: Sequence[int], *, sample_rate: int) -> dict[str, int]:
    if not samples:
        return {"bytes": 0, "samples": 0, "duration_ms": 0, "rms": 0, "peak": 0}
    duration_ms = int((len(samples) * 1000) / max(sample_rate, 1))
    peak = max(abs(sample) for sample in samples)
    energy = sum(int(sample) * int(sample) for sample in samples)
    rms = int(math.sqrt(energy / len(samples))) if energy > 0 else 0
    return {
        "bytes": len(samples) * 2,
        "samples": len(samples),
        "duration_ms": duration_ms,
        "rms": rms,
        "peak": peak,
    }


@dataclass
class LinearPcmResampler:
    source_rate: int
    target_rate: int
    _last_sample: int | None = field(default=None, init=False, repr=False)
    _next_output_position: float = field(default=0.0, init=False, repr=False)

    def resample(self, samples: Sequence[int]) -> list[int]:
        if not samples:
            return []
        if self.source_rate == self.target_rate:
            return list(samples)

        if self._last_sample is None:
            combined = list(samples)
        else:
            combined = [self._last_sample, *samples]

        if len(combined) < 2:
            self._last_sample = combined[-1]
            return []

        step = self.source_rate / self.target_rate
        max_position = len(combined) - 1
        output: list[int] = []
        position = self._next_output_position

        while position < max_position:
            base_index = int(position)
            fraction = position - base_index
            left = combined[base_index]
            right = combined[base_index + 1]
            interpolated = left if fraction <= 1e-9 else left + ((right - left) * fraction)
            output.append(_clamp_pcm16(interpolated))
            position += step

        self._next_output_position = position - max_position
        self._last_sample = combined[-1]
        return output


@dataclass(frozen=True)
class DecodedTwilioInboundAudio:
    pcm8k: bytes
    pcm16k: bytes
    rms: int


@dataclass
class TwilioMediaAudioCodec:
    input_batch_ms: int = 100
    twilio_frame_bytes: int = 160
    _inbound_resampler: LinearPcmResampler = field(init=False, repr=False)
    _outbound_resampler: LinearPcmResampler = field(init=False, repr=False)
    _pending_inbound_pcm16k: bytearray = field(default_factory=bytearray, init=False, repr=False)
    _input_batch_bytes: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._inbound_resampler = LinearPcmResampler(
            source_rate=_TWILIO_INPUT_SAMPLE_RATE,
            target_rate=_GEMINI_INPUT_SAMPLE_RATE,
        )
        self._outbound_resampler = LinearPcmResampler(
            source_rate=_DEFAULT_MODEL_OUTPUT_SAMPLE_RATE,
            target_rate=_TWILIO_OUTPUT_SAMPLE_RATE,
        )
        batch_ms = max(20, int(self.input_batch_ms or 20))
        bytes_per_ms = (_GEMINI_INPUT_SAMPLE_RATE * 2) / 1000
        aligned_batch_bytes = int(batch_ms * bytes_per_ms)
        if aligned_batch_bytes % 2 != 0:
            aligned_batch_bytes += 1
        self._input_batch_bytes = max(640, aligned_batch_bytes)

    @property
    def pending_inbound_bytes(self) -> int:
        return len(self._pending_inbound_pcm16k)

    def decode_twilio_payload(self, encoded_payload: str) -> DecodedTwilioInboundAudio:
        encoded = (encoded_payload or "").strip()
        if not encoded:
            raise ValueError("Twilio media payload is empty.")

        padding = (-len(encoded)) % 4
        if padding:
            encoded += "=" * padding
        ulaw_bytes = base64.b64decode(encoded.encode("ascii"), validate=False)
        pcm8_samples = ulaw_bytes_to_samples(ulaw_bytes)
        stats = compute_pcm16_stats(pcm8_samples, sample_rate=_TWILIO_INPUT_SAMPLE_RATE)
        pcm16k_samples = self._inbound_resampler.resample(pcm8_samples)
        return DecodedTwilioInboundAudio(
            pcm8k=_samples_to_pcm16_bytes(pcm8_samples),
            pcm16k=_samples_to_pcm16_bytes(pcm16k_samples),
            rms=stats["rms"],
        )

    def queue_inbound_audio(self, pcm16k: bytes) -> list[bytes]:
        if not pcm16k:
            return []
        self._pending_inbound_pcm16k.extend(pcm16k)
        batches: list[bytes] = []
        while len(self._pending_inbound_pcm16k) >= self._input_batch_bytes:
            batches.append(bytes(self._pending_inbound_pcm16k[: self._input_batch_bytes]))
            del self._pending_inbound_pcm16k[: self._input_batch_bytes]
        return batches

    def flush_inbound_audio(self) -> bytes | None:
        if not self._pending_inbound_pcm16k:
            return None
        flushed = bytes(self._pending_inbound_pcm16k)
        self._pending_inbound_pcm16k.clear()
        return flushed

    def encode_model_audio(self, pcm_bytes: bytes, *, mime_type: str | None) -> list[bytes]:
        if not pcm_bytes:
            return []

        source_rate = _extract_audio_rate(mime_type, default=_DEFAULT_MODEL_OUTPUT_SAMPLE_RATE)
        source_samples = pcm16_bytes_to_samples(pcm_bytes)
        if source_rate != self._outbound_resampler.source_rate:
            self._outbound_resampler = LinearPcmResampler(
                source_rate=source_rate,
                target_rate=_TWILIO_OUTPUT_SAMPLE_RATE,
            )
        pcm8_samples = self._outbound_resampler.resample(source_samples)
        ulaw = samples_to_ulaw_bytes(pcm8_samples)
        return _chunk_bytes(ulaw, self.twilio_frame_bytes)
