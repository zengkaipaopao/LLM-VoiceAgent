from __future__ import annotations

import audioop
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
    conditioned_rms: int


@dataclass
class PcmNoiseGate:
    sample_rate: int
    enabled: bool = True
    open_rms: int = 140
    close_rms: int = 90
    frame_ms: int = 20
    hold_ms: int = 240
    _gate_open: bool = field(default=False, init=False, repr=False)
    _hold_frames_remaining: int = field(default=0, init=False, repr=False)
    _frame_samples: int = field(default=0, init=False, repr=False)
    _hold_frames: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._frame_samples = max(1, int((self.sample_rate * max(1, self.frame_ms)) / 1000))
        self._hold_frames = max(0, int(max(0, self.hold_ms) / max(1, self.frame_ms)))

    def process(self, pcm16_bytes: bytes) -> bytes:
        if not self.enabled or not pcm16_bytes:
            return pcm16_bytes

        samples = pcm16_bytes_to_samples(pcm16_bytes)
        if not samples:
            return pcm16_bytes

        output: list[int] = []
        for index in range(0, len(samples), self._frame_samples):
            frame = samples[index : index + self._frame_samples]
            if not frame:
                continue
            rms = compute_pcm16_stats(frame, sample_rate=self.sample_rate)["rms"]
            keep_frame = False

            if self._gate_open:
                if rms >= self.close_rms:
                    self._hold_frames_remaining = self._hold_frames
                    keep_frame = True
                elif self._hold_frames_remaining > 0:
                    self._hold_frames_remaining -= 1
                    keep_frame = True
                else:
                    self._gate_open = False

            if not self._gate_open and rms >= self.open_rms:
                self._gate_open = True
                self._hold_frames_remaining = self._hold_frames
                keep_frame = True

            if keep_frame:
                output.extend(frame)
            else:
                output.extend(0 for _ in frame)

        return _samples_to_pcm16_bytes(output)


@dataclass
class TwilioMediaAudioCodec:
    input_batch_ms: int = 100
    twilio_frame_bytes: int = 160
    input_noise_gate_enabled: bool = True
    input_noise_gate_open_rms: int = 140
    input_noise_gate_close_rms: int = 90
    input_noise_gate_hold_ms: int = 240
    _inbound_resampler: LinearPcmResampler = field(init=False, repr=False)
    _outbound_resampler: LinearPcmResampler = field(init=False, repr=False)
    _input_noise_gate: PcmNoiseGate = field(init=False, repr=False)
    _audioop_inbound_state: object | None = field(default=None, init=False, repr=False)
    _audioop_outbound_state: object | None = field(default=None, init=False, repr=False)
    _audioop_outbound_source_rate: int = field(
        default=_DEFAULT_MODEL_OUTPUT_SAMPLE_RATE,
        init=False,
        repr=False,
    )
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
        self._input_noise_gate = PcmNoiseGate(
            sample_rate=_TWILIO_INPUT_SAMPLE_RATE,
            enabled=bool(self.input_noise_gate_enabled),
            open_rms=max(0, int(self.input_noise_gate_open_rms or 0)),
            close_rms=max(0, int(self.input_noise_gate_close_rms or 0)),
            hold_ms=max(0, int(self.input_noise_gate_hold_ms or 0)),
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
        pcm8k_bytes = audioop.ulaw2lin(ulaw_bytes, 2)
        pcm8_samples = pcm16_bytes_to_samples(pcm8k_bytes)
        stats = compute_pcm16_stats(pcm8_samples, sample_rate=_TWILIO_INPUT_SAMPLE_RATE)
        conditioned_pcm8k_bytes = self._input_noise_gate.process(pcm8k_bytes)
        conditioned_pcm8_samples = pcm16_bytes_to_samples(conditioned_pcm8k_bytes)
        conditioned_stats = compute_pcm16_stats(
            conditioned_pcm8_samples,
            sample_rate=_TWILIO_INPUT_SAMPLE_RATE,
        )
        pcm16k_bytes, self._audioop_inbound_state = audioop.ratecv(
            conditioned_pcm8k_bytes,
            2,
            1,
            _TWILIO_INPUT_SAMPLE_RATE,
            _GEMINI_INPUT_SAMPLE_RATE,
            self._audioop_inbound_state,
        )
        return DecodedTwilioInboundAudio(
            pcm8k=pcm8k_bytes,
            pcm16k=pcm16k_bytes,
            rms=stats["rms"],
            conditioned_rms=conditioned_stats["rms"],
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
        aligned_pcm_bytes = pcm_bytes if len(pcm_bytes) % 2 == 0 else pcm_bytes[:-1]
        if not aligned_pcm_bytes:
            return []

        source_samples = pcm16_bytes_to_samples(aligned_pcm_bytes)
        if source_rate != self._outbound_resampler.source_rate:
            self._outbound_resampler = LinearPcmResampler(
                source_rate=source_rate,
                target_rate=_TWILIO_OUTPUT_SAMPLE_RATE,
            )
        if source_rate != self._audioop_outbound_source_rate:
            self._audioop_outbound_source_rate = source_rate
            self._audioop_outbound_state = None
        if source_samples:
            pcm8k_bytes, self._audioop_outbound_state = audioop.ratecv(
                aligned_pcm_bytes,
                2,
                1,
                source_rate,
                _TWILIO_OUTPUT_SAMPLE_RATE,
                self._audioop_outbound_state,
            )
        else:
            pcm8k_bytes = b""
        ulaw = audioop.lin2ulaw(pcm8k_bytes, 2) if pcm8k_bytes else b""
        return _chunk_bytes(ulaw, self.twilio_frame_bytes)
