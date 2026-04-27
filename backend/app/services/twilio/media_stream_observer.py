from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.services.twilio.debug_audio_capture import RollingPcmCapture, SavedInboundDebugAudio

AppendTraceCallback = Callable[..., Awaitable[None]]
AppendManualActivityTraceCallback = Callable[..., Awaitable[None]]


@dataclass(slots=True)
class TwilioMediaStreamObserver:
    call_sid: str | None
    debug_wav_enabled: bool
    debug_output_dir: str
    followup_capture_seconds: int
    followup_rms_threshold: int
    followup_min_hits: int
    inbound_debug_captures: dict[str, RollingPcmCapture]
    followup_debug_captures: dict[str, RollingPcmCapture]
    inbound_debug_capture_saved_variants: set[str] = field(default_factory=set)
    followup_probe_armed: bool = False
    followup_probe_started_at: float = 0.0
    followup_probe_detection_hits: int = 0
    followup_probe_capture_started: bool = False
    followup_probe_capture_saved: bool = False
    followup_probe_capture_started_at: float = 0.0
    followup_probe_transcript_observed: bool = False
    _inbound_debug_capture_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )
    _followup_debug_capture_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    def bind_call_sid(self, call_sid: str | None) -> None:
        self.call_sid = (call_sid or "").strip() or None

    def append_inbound_audio(self, *, pcm8k: bytes, pcm16k: bytes) -> None:
        capture8k = self.inbound_debug_captures.get("pcm8k_raw")
        capture16k = self.inbound_debug_captures.get("pcm16k_resampled")
        if capture8k is not None:
            capture8k.append(pcm8k)
        if capture16k is not None:
            capture16k.append(pcm16k)

    def note_followup_transcript_observed(self) -> None:
        if self.followup_probe_started_at > 0.0:
            self.followup_probe_transcript_observed = True

    async def arm_followup_probe(
        self,
        *,
        trigger: str,
        append_trace: AppendTraceCallback,
    ) -> None:
        self.followup_probe_armed = True
        self.followup_probe_started_at = asyncio.get_running_loop().time()
        self.followup_probe_detection_hits = 0
        self.followup_probe_capture_started = False
        self.followup_probe_capture_saved = False
        self.followup_probe_capture_started_at = 0.0
        self.followup_probe_transcript_observed = False
        self._reset_followup_probe_captures()
        await self._append_trace(
            append_trace,
            event_type="followup_probe_armed",
            text=f"trigger={trigger} rms_threshold={self.followup_rms_threshold}",
            level="info",
        )

    async def disarm_followup_probe(
        self,
        *,
        reason: str,
        append_trace: AppendTraceCallback,
        append_manual_activity_trace: AppendManualActivityTraceCallback | None = None,
        manual_activity_control: bool = False,
        manual_activity_active: bool = False,
    ) -> None:
        if self.followup_probe_capture_started and not self.followup_probe_capture_saved:
            await self.persist_followup_debug_wav(
                trigger=reason,
                append_trace=append_trace,
                append_manual_activity_trace=append_manual_activity_trace,
                manual_activity_control=manual_activity_control,
                manual_activity_active=manual_activity_active,
            )
        self.followup_probe_armed = False
        self.followup_probe_detection_hits = 0
        self.followup_probe_capture_started = False
        self.followup_probe_capture_started_at = 0.0
        self.followup_probe_transcript_observed = False

    async def observe_followup_audio(
        self,
        *,
        now_ts: float,
        rms: int,
        pcm8k: bytes,
        pcm16k: bytes,
        append_trace: AppendTraceCallback,
        append_manual_activity_trace: AppendManualActivityTraceCallback | None = None,
        manual_activity_control: bool = False,
        manual_activity_active: bool = False,
    ) -> None:
        if not self.followup_probe_armed:
            return

        if not self.followup_probe_capture_started:
            if rms >= self.followup_rms_threshold:
                self.followup_probe_detection_hits += 1
            else:
                self.followup_probe_detection_hits = 0
            if self.followup_probe_detection_hits >= self.followup_min_hits:
                self.followup_probe_capture_started = True
                self.followup_probe_capture_started_at = now_ts
                await self._append_trace(
                    append_trace,
                    event_type="followup_probe_speech_detected",
                    text=(
                        f"rms={rms} after_ms="
                        f"{int((now_ts - self.followup_probe_started_at) * 1000)}"
                    ),
                    level="warning",
                )

        if not self.followup_probe_capture_started:
            return

        capture8k = self.followup_debug_captures.get("followup_pcm8k_raw")
        capture16k = self.followup_debug_captures.get("followup_pcm16k_resampled")
        if capture8k is not None:
            capture8k.append(pcm8k)
        if capture16k is not None:
            capture16k.append(pcm16k)

        if (
            not self.followup_probe_capture_saved
            and self.followup_debug_captures
            and all(capture.is_full for capture in self.followup_debug_captures.values())
        ):
            await self.persist_followup_debug_wav(
                trigger="followup_probe_full",
                append_trace=append_trace,
                append_manual_activity_trace=append_manual_activity_trace,
                manual_activity_control=manual_activity_control,
                manual_activity_active=manual_activity_active,
            )
            self.followup_probe_armed = False
            self.followup_probe_detection_hits = 0
            self.followup_probe_capture_started = False
            self.followup_probe_capture_started_at = 0.0

    async def persist_inbound_debug_wav(
        self,
        *,
        trigger: str,
        append_trace: AppendTraceCallback,
    ) -> None:
        if not self.debug_wav_enabled or not self.call_sid:
            return

        async with self._inbound_debug_capture_lock:
            remaining_variants = [
                variant
                for variant, capture in self.inbound_debug_captures.items()
                if variant not in self.inbound_debug_capture_saved_variants and capture.has_audio()
            ]
            if not remaining_variants:
                if (
                    not self.inbound_debug_capture_saved_variants
                    and not any(capture.has_audio() for capture in self.inbound_debug_captures.values())
                ):
                    self.inbound_debug_capture_saved_variants = set(self.inbound_debug_captures.keys())
                    await self._append_trace(
                        append_trace,
                        event_type="inbound_debug_wav_skipped",
                        text=f"trigger={trigger} reason=no_inbound_audio",
                        level="info",
                    )
                return

            try:
                saved_audio_items = await self._save_capture_variants(
                    captures=self.inbound_debug_captures,
                    variants=remaining_variants,
                )
            except Exception as exc:
                await self._append_trace(
                    append_trace,
                    event_type="inbound_debug_wav_error",
                    text=f"trigger={trigger} error={exc}",
                    level="warning",
                )
                return

            if not saved_audio_items:
                await self._append_trace(
                    append_trace,
                    event_type="inbound_debug_wav_skipped",
                    text=f"trigger={trigger} reason=empty_capture",
                    level="info",
                )
                return

            self.inbound_debug_capture_saved_variants.update(variant for variant, _ in saved_audio_items)
            await self._append_trace(
                append_trace,
                event_type="inbound_debug_wav_saved",
                text=self._format_saved_audio_trace(trigger=trigger, saved_audio_items=saved_audio_items),
                level="success",
            )

    async def persist_followup_debug_wav(
        self,
        *,
        trigger: str,
        append_trace: AppendTraceCallback,
        append_manual_activity_trace: AppendManualActivityTraceCallback | None = None,
        manual_activity_control: bool = False,
        manual_activity_active: bool = False,
    ) -> None:
        if not self.debug_wav_enabled or not self.call_sid:
            return

        async with self._followup_debug_capture_lock:
            try:
                saved_audio_items = await self._save_capture_variants(
                    captures=self.followup_debug_captures,
                    variants=tuple(self.followup_debug_captures.keys()),
                )
            except Exception as exc:
                await self._append_trace(
                    append_trace,
                    event_type="followup_debug_wav_error",
                    text=f"trigger={trigger} error={exc}",
                    level="warning",
                )
                return

            if not saved_audio_items:
                return

            self.followup_probe_capture_saved = True
            await self._append_trace(
                append_trace,
                event_type="followup_debug_wav_saved",
                text=self._format_saved_audio_trace(trigger=trigger, saved_audio_items=saved_audio_items),
                level="success",
            )
            if not self.followup_probe_transcript_observed:
                if (
                    append_manual_activity_trace is not None
                    and manual_activity_control
                    and manual_activity_active
                ):
                    await append_manual_activity_trace(
                        event_type="manual_activity_end_overdue",
                        reason=f"{trigger}_no_input_transcript",
                        level="warning",
                    )
                await self._append_trace(
                    append_trace,
                    event_type="gemini_turn_detection_stalled",
                    text=(
                        f"trigger={trigger} capture_seconds={self.followup_capture_seconds} "
                        "followup_audio_detected_but_no_new_input_transcript"
                    ),
                    level="warning",
                )

    async def _save_capture_variants(
        self,
        *,
        captures: dict[str, RollingPcmCapture],
        variants: tuple[str, ...] | list[str],
    ) -> list[tuple[str, SavedInboundDebugAudio]]:
        saved_audio_items: list[tuple[str, SavedInboundDebugAudio]] = []
        for variant in variants:
            capture = captures.get(variant)
            if capture is None or not capture.has_audio():
                continue
            saved_audio = await asyncio.to_thread(
                capture.save_wav,
                output_dir=self.debug_output_dir,
                call_sid=self.call_sid,
            )
            if saved_audio:
                saved_audio_items.append((variant, saved_audio))
        return saved_audio_items

    def _reset_followup_probe_captures(self) -> None:
        for capture in self.followup_debug_captures.values():
            capture.reset()

    def _format_saved_audio_trace(
        self,
        *,
        trigger: str,
        saved_audio_items: list[tuple[str, SavedInboundDebugAudio]],
    ) -> str:
        return " ; ".join(
            [
                (
                    f"trigger={trigger} variant={variant} duration_ms={saved_audio.duration_ms} "
                    f"sample_rate={saved_audio.sample_rate} bytes={saved_audio.bytes} "
                    f"path={saved_audio.path}"
                )
                for variant, saved_audio in saved_audio_items
            ]
        )

    async def _append_trace(
        self,
        append_trace: AppendTraceCallback,
        *,
        event_type: str,
        text: str,
        level: str,
    ) -> None:
        if not self.call_sid:
            return
        await append_trace(
            self.call_sid,
            event_type=event_type,
            text=text,
            level=level,
        )
