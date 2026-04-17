from __future__ import annotations

import re
import wave
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


_FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_token(value: str | None, *, fallback: str) -> str:
    normalized = _FILENAME_SAFE_PATTERN.sub("-", (value or "").strip()).strip("-._")
    return normalized or fallback


@dataclass(frozen=True)
class SavedInboundDebugAudio:
    call_sid: str
    artifact_key: str
    path: str
    bytes: int
    duration_ms: int
    sample_rate: int


@dataclass
class RollingPcmCapture:
    sample_rate: int = 16000
    channels: int = 1
    sample_width_bytes: int = 2
    duration_seconds: int = 5
    artifact_key: str = "inbound-pcm16k"
    _chunks: deque[bytes] = field(default_factory=deque, init=False, repr=False)
    _total_bytes: int = field(default=0, init=False, repr=False)

    @property
    def max_bytes(self) -> int:
        return (
            max(self.sample_rate, 1)
            * max(self.channels, 1)
            * max(self.sample_width_bytes, 1)
            * max(int(self.duration_seconds or 0), 0)
        )

    def append(self, pcm_bytes: bytes) -> None:
        if not pcm_bytes or self.max_bytes <= 0:
            return
        self._chunks.append(bytes(pcm_bytes))
        self._total_bytes += len(pcm_bytes)
        self._trim_left()

    def has_audio(self) -> bool:
        return self._total_bytes > 0

    def build_bytes(self) -> bytes:
        if not self._chunks:
            return b""
        return b"".join(self._chunks)

    def build_output_path(self, *, output_dir: str | Path, call_sid: str | None) -> Path:
        safe_call_sid = _safe_token(call_sid, fallback="unknown-call")
        safe_artifact_key = _safe_token(self.artifact_key, fallback="audio")
        return Path(output_dir).expanduser().resolve() / f"{safe_call_sid}.{safe_artifact_key}.wav"

    def save_wav(self, *, output_dir: str | Path, call_sid: str | None) -> SavedInboundDebugAudio | None:
        audio_bytes = self.build_bytes()
        if not audio_bytes:
            return None

        output_path = self.build_output_path(output_dir=output_dir, call_sid=call_sid)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width_bytes)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_bytes)

        duration_ms = int(
            len(audio_bytes) * 1000 / max(self.sample_rate * self.channels * self.sample_width_bytes, 1)
        )
        return SavedInboundDebugAudio(
            call_sid=(call_sid or "").strip(),
            artifact_key=self.artifact_key,
            path=str(output_path),
            bytes=len(audio_bytes),
            duration_ms=duration_ms,
            sample_rate=self.sample_rate,
        )

    def _trim_left(self) -> None:
        overflow = self._total_bytes - self.max_bytes
        while overflow > 0 and self._chunks:
            head = self._chunks[0]
            if len(head) <= overflow:
                self._chunks.popleft()
                self._total_bytes -= len(head)
                overflow -= len(head)
                continue

            self._chunks[0] = head[overflow:]
            self._total_bytes -= overflow
            overflow = 0


RollingInboundPcm16Capture = RollingPcmCapture
