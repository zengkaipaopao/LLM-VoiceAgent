from __future__ import annotations

import asyncio
import audioop
import base64
import io
import wave
from dataclasses import dataclass
from typing import Any

from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.google_genai_client import create_google_genai_client
from app.services.twilio.audio_codec import PcmNoiseGate
from app.services.twilio.live_config import _build_gemini_live_config
from app.services.twilio.prompt_runtime_helpers import (
    _build_twilio_session_instruction,
    _extract_opening_sentence,
    _resolve_gemini_live_model,
    _resolve_prompt_runtime,
)
from app.services.twilio.stream_runtime_store import _chunk_bytes, _pcm16_audio_stats

_PCM_SAMPLE_WIDTH_BYTES = 2
_DEFAULT_INPUT_SAMPLE_RATE = 16000
_TWILIO_SAMPLE_RATE = 8000
_GEMINI_SAMPLE_RATE = 16000
_LIVE_AUDIO_CHUNK_BYTES = 640
_LIVE_EVALUATION_TIMEOUT_SECONDS = 18.0


@dataclass(frozen=True, slots=True)
class AudioLabVariant:
    variant_id: str
    label: str
    description: str
    sample_rate: int
    pcm_bytes: bytes
    wav_bytes: bytes
    stats: dict[str, int]

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.variant_id,
            "label": self.label,
            "description": self.description,
            "sample_rate": self.sample_rate,
            "pcm_mime_type": f"audio/pcm;rate={self.sample_rate}",
            "duration_ms": int(self.stats.get("duration_ms") or 0),
            "bytes": int(self.stats.get("bytes") or 0),
            "rms": int(self.stats.get("rms") or 0),
            "peak": int(self.stats.get("peak") or 0),
            "pcm_base64": base64.b64encode(self.pcm_bytes).decode("ascii"),
            "wav_base64": base64.b64encode(self.wav_bytes).decode("ascii"),
        }


def _normalize_pcm16_bytes(audio_bytes: bytes) -> bytes:
    if not audio_bytes:
        return b""
    return audio_bytes if len(audio_bytes) % 2 == 0 else audio_bytes[:-1]


def decode_audio_base64_payload(encoded: str) -> bytes:
    token = (encoded or "").strip()
    if not token:
        raise ValueError("audio_base64 is empty.")
    padding = (-len(token)) % 4
    if padding:
        token += "=" * padding
    decoded = base64.b64decode(token.encode("ascii"), validate=False)
    normalized = _normalize_pcm16_bytes(decoded)
    if not normalized:
        raise ValueError("Decoded PCM payload is empty.")
    return normalized


def _resample_pcm16(audio_bytes: bytes, *, source_rate: int, target_rate: int) -> bytes:
    normalized = _normalize_pcm16_bytes(audio_bytes)
    if not normalized:
        return b""
    if source_rate == target_rate:
        return normalized
    converted, _ = audioop.ratecv(
        normalized,
        _PCM_SAMPLE_WIDTH_BYTES,
        1,
        int(source_rate),
        int(target_rate),
        None,
    )
    return _normalize_pcm16_bytes(converted)


def _build_wav_bytes(audio_bytes: bytes, *, sample_rate: int) -> bytes:
    normalized = _normalize_pcm16_bytes(audio_bytes)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(_PCM_SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(normalized)
    return buffer.getvalue()


def prepare_audio_lab_variants(*, audio_bytes: bytes, sample_rate: int) -> list[AudioLabVariant]:
    normalized = _normalize_pcm16_bytes(audio_bytes)
    resolved_sample_rate = max(4000, int(sample_rate or _DEFAULT_INPUT_SAMPLE_RATE))
    if not normalized:
        raise ValueError("Audio payload is empty.")

    twilio_input_pcm8k = _resample_pcm16(
        normalized,
        source_rate=resolved_sample_rate,
        target_rate=_TWILIO_SAMPLE_RATE,
    )
    twilio_ulaw = audioop.lin2ulaw(twilio_input_pcm8k, _PCM_SAMPLE_WIDTH_BYTES)
    twilio_preview_pcm8k = audioop.ulaw2lin(twilio_ulaw, _PCM_SAMPLE_WIDTH_BYTES)

    input_gate = PcmNoiseGate(
        sample_rate=_TWILIO_SAMPLE_RATE,
        enabled=bool(settings.twilio_media_stream_input_noise_gate_enabled),
        open_rms=max(0, int(settings.twilio_media_stream_input_noise_gate_open_rms or 0)),
        close_rms=max(0, int(settings.twilio_media_stream_input_noise_gate_close_rms or 0)),
        hold_ms=max(0, int(settings.twilio_media_stream_input_noise_gate_hold_ms or 0)),
    )
    conditioned_pcm8k = input_gate.process(twilio_preview_pcm8k)
    gemini_preview_pcm16k = _resample_pcm16(
        conditioned_pcm8k,
        source_rate=_TWILIO_SAMPLE_RATE,
        target_rate=_GEMINI_SAMPLE_RATE,
    )

    variants = [
        AudioLabVariant(
            variant_id="original_recording",
            label="原始录音",
            description="浏览器录下的原始单声道 PCM 录音，未经过电话链路退化。",
            sample_rate=resolved_sample_rate,
            pcm_bytes=normalized,
            wav_bytes=_build_wav_bytes(normalized, sample_rate=resolved_sample_rate),
            stats=_pcm16_audio_stats(normalized, sample_rate=resolved_sample_rate),
        ),
        AudioLabVariant(
            variant_id="twilio_preview",
            label="送给 Twilio 的电话版",
            description=(
                "模拟 16k/PCM 进入电话链路后，经过 8k 降采样与 μ-law 编解码后的听感。"
            ),
            sample_rate=_TWILIO_SAMPLE_RATE,
            pcm_bytes=twilio_preview_pcm8k,
            wav_bytes=_build_wav_bytes(twilio_preview_pcm8k, sample_rate=_TWILIO_SAMPLE_RATE),
            stats=_pcm16_audio_stats(twilio_preview_pcm8k, sample_rate=_TWILIO_SAMPLE_RATE),
        ),
        AudioLabVariant(
            variant_id="gemini_preview",
            label="送给 Gemini 的上送版",
            description=(
                "模拟电话入站经 μ-law 解码、输入门控与 8k→16k 升采样后，真正上送给 Gemini Live 的版本。"
            ),
            sample_rate=_GEMINI_SAMPLE_RATE,
            pcm_bytes=gemini_preview_pcm16k,
            wav_bytes=_build_wav_bytes(gemini_preview_pcm16k, sample_rate=_GEMINI_SAMPLE_RATE),
            stats=_pcm16_audio_stats(gemini_preview_pcm16k, sample_rate=_GEMINI_SAMPLE_RATE),
        ),
    ]
    return variants


async def evaluate_audio_with_gemini_live(
    *,
    db: AsyncSession,
    audio_bytes: bytes,
    sample_rate: int,
    prompt_code: str | None,
    voice_name: str | None,
    opening_already_played: bool,
) -> dict[str, Any]:
    normalized = _normalize_pcm16_bytes(audio_bytes)
    resolved_sample_rate = max(4000, int(sample_rate or _DEFAULT_INPUT_SAMPLE_RATE))
    if not normalized:
        raise ValueError("Audio payload is empty.")

    send_pcm16k = _resample_pcm16(
        normalized,
        source_rate=resolved_sample_rate,
        target_rate=_GEMINI_SAMPLE_RATE,
    )
    if not send_pcm16k:
        raise ValueError("Audio payload becomes empty after resampling.")

    runtime = await _resolve_prompt_runtime(
        db=db,
        prompt_code=prompt_code,
        model_capability="live",
    )
    selected_model = _resolve_gemini_live_model(
        runtime.template.llm_model if runtime.template is not None else None
    )
    system_instruction = runtime.system_instruction
    opening_text = _extract_opening_sentence(system_instruction) if opening_already_played else None
    effective_instruction = _build_twilio_session_instruction(
        system_instruction,
        opening_text=opening_text,
    )
    live_config = _build_gemini_live_config(
        model=selected_model,
        system_instruction=effective_instruction,
        voice_name=(voice_name or "").strip() or None,
        manual_vad=True,
        media_stream_bridge_profile="legacy_manual",
    )
    client = create_google_genai_client()

    input_partials: list[str] = []
    output_partials: list[str] = []
    assistant_meta_texts: list[str] = []
    input_final = ""
    output_final = ""
    session_id = ""
    turn_complete = False
    timed_out = False
    usage: dict[str, int] | None = None
    event_types: list[str] = []

    def _append_unique(bucket: list[str], text: str | None) -> None:
        value = (text or "").strip()
        if not value:
            return
        if bucket and bucket[-1] == value:
            return
        bucket.append(value)

    async with client.aio.live.connect(model=selected_model, config=live_config) as session:
        await session.send_realtime_input(activity_start=types.ActivityStart())
        for chunk in _chunk_bytes(send_pcm16k, _LIVE_AUDIO_CHUNK_BYTES):
            await session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
            )
        await session.send_realtime_input(activity_end=types.ActivityEnd())

        try:
            async with asyncio.timeout(_LIVE_EVALUATION_TIMEOUT_SECONDS):
                async for message in session.receive():
                    if message.setup_complete:
                        session_id = str(message.setup_complete.session_id or "").strip()
                        event_types.append("setup_complete")

                    if message.usage_metadata:
                        usage = {
                            "total_tokens": int(message.usage_metadata.total_token_count or 0),
                            "prompt_tokens": int(message.usage_metadata.prompt_token_count or 0),
                            "response_tokens": int(message.usage_metadata.response_token_count or 0),
                        }
                        event_types.append("usage")

                    content = message.server_content
                    if not content:
                        continue

                    if content.input_transcription and content.input_transcription.text:
                        if content.input_transcription.finished:
                            input_final = content.input_transcription.text.strip()
                            event_types.append("input_transcript_final")
                        else:
                            _append_unique(input_partials, content.input_transcription.text)
                            event_types.append("input_transcript_partial")

                    if content.output_transcription and content.output_transcription.text:
                        if content.output_transcription.finished:
                            output_final = content.output_transcription.text.strip()
                            event_types.append("output_transcript_final")
                        else:
                            _append_unique(output_partials, content.output_transcription.text)
                            event_types.append("output_transcript_partial")

                    if content.model_turn and content.model_turn.parts:
                        for part in content.model_turn.parts:
                            if part.text:
                                _append_unique(assistant_meta_texts, part.text)
                                event_types.append("assistant_meta_text")

                    if content.turn_complete:
                        turn_complete = True
                        event_types.append("turn_complete")
                        if not output_final and output_partials:
                            output_final = output_partials[-1]
                        if not input_final and input_partials:
                            input_final = input_partials[-1]
                        break
        except TimeoutError:
            timed_out = True

        if not turn_complete and not timed_out:
            timed_out = True

    return {
        "prompt_code": runtime.template_code,
        "model": selected_model,
        "session_id": session_id or None,
        "opening_already_played": bool(opening_already_played),
        "opening_text": opening_text,
        "original_sample_rate": resolved_sample_rate,
        "effective_send_sample_rate": _GEMINI_SAMPLE_RATE,
        "input_partials": input_partials,
        "input_final": input_final,
        "output_partials": output_partials,
        "output_final": output_final,
        "assistant_meta_texts": assistant_meta_texts,
        "turn_complete": turn_complete,
        "timed_out": timed_out,
        "usage": usage,
        "event_types": event_types,
    }
