from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.twilio.audio_codec import DecodedTwilioInboundAudio
from app.services.twilio.gemini_live_session_adapter import GeminiLiveSessionAdapter
from app.services.twilio.manual_activity_controller import TwilioManualActivityController

AppendTraceCallback = Callable[..., Awaitable[None]]


@dataclass(slots=True)
class TwilioManualActivityBridgeService:
    controller: TwilioManualActivityController
    live_input: GeminiLiveSessionAdapter
    append_trace: AppendTraceCallback

    @property
    def active(self) -> bool:
        return self.controller.active

    @property
    def start_rms(self) -> int:
        return self.controller.start_rms

    @property
    def end_rms(self) -> int:
        return self.controller.end_rms

    @property
    def barge_rms(self) -> int:
        return self.controller.barge_rms

    @property
    def prefix_padding_ms(self) -> int:
        return self.controller.prefix_padding_ms

    async def append_activity_trace(
        self,
        *,
        current_call_sid: str | None,
        event_type: str,
        reason: str,
        level: str = "info",
        now_ts: float | None = None,
        silence_ms: int | None = None,
    ) -> None:
        if not current_call_sid:
            return
        trace_text = self.controller.build_trace_text(
            reason=reason,
            now_ts=now_ts,
            silence_ms=silence_ms,
        )
        if not trace_text:
            return
        await self.append_trace(
            current_call_sid,
            event_type=event_type,
            text=trace_text,
            level=level,
        )

    async def start_activity(
        self,
        *,
        current_call_sid: str | None,
        now_ts: float,
        mode: str,
        threshold: int,
        raw_rms: int,
        conditioned_rms: int,
        prefix_payload: bytes,
    ) -> None:
        self.controller.begin_activity(
            now_ts=now_ts,
            raw_rms=raw_rms,
            conditioned_rms=conditioned_rms,
        )
        await self.live_input.queue_activity_start()
        if prefix_payload:
            await self.live_input.queue_pcm16k_payload(prefix_payload)
        await self.append_trace(
            current_call_sid,
            event_type="manual_activity_start_sent",
            text=(
                f"raw_rms={raw_rms} conditioned_rms={conditioned_rms} "
                f"threshold={threshold} end_threshold={self.controller.end_rms} "
                f"prefix_ms={self.controller.prefix_padding_ms} mode={mode}"
            ),
            level="info",
        )

    async def send_end(
        self,
        *,
        current_call_sid: str | None,
        reason: str,
        silence_ms: int | None = None,
    ) -> None:
        if not self.controller.active:
            self.controller.reset_all()
            return
        await self.live_input.flush_pending_audio()
        await self.live_input.queue_activity_end()
        await self.append_activity_trace(
            current_call_sid=current_call_sid,
            event_type="manual_activity_end_sent",
            reason=reason,
            silence_ms=silence_ms,
        )
        self.controller.reset_all()

    async def close_input(self, *, current_call_sid: str | None) -> None:
        if self.controller.active:
            await self.send_end(current_call_sid=current_call_sid, reason="stream_close")
        await self.live_input.close_input()

    async def handle_media_frame(
        self,
        *,
        current_call_sid: str | None,
        decoded_audio: DecodedTwilioInboundAudio,
        now_ts: float,
        playback_locked: bool,
        legacy_manual_vad: bool,
        half_duplex_manual_turn_control: bool,
    ) -> None:
        # TODO(media-stream-v2): 如果后续确认 profile 长期只保留 half-duplex/no-interruption，
        # 这里还可以继续拆成 “start policy” 和 “active window policy” 两段，
        # 让 legacy_manual_vad / half_duplex_manual_turn_control 不再混在同一入口里分支。
        if legacy_manual_vad and playback_locked and not self.controller.active:
            prefix_payload = self.controller.observe_barge_in_candidate(
                pcm16k=decoded_audio.pcm16k,
                raw_rms=decoded_audio.rms,
            )
            if prefix_payload:
                await self.start_activity(
                    current_call_sid=current_call_sid,
                    now_ts=now_ts,
                    mode="barge_in_during_playback",
                    threshold=self.controller.barge_rms,
                    raw_rms=decoded_audio.rms,
                    conditioned_rms=decoded_audio.conditioned_rms,
                    prefix_payload=prefix_payload,
                )
            return

        if half_duplex_manual_turn_control and playback_locked:
            self.controller.drop_while_playing()
            return

        if not self.controller.active:
            prefix_payload = self.controller.observe_normal_start_candidate(
                pcm16k=decoded_audio.pcm16k,
                raw_rms=decoded_audio.rms,
            )
            if prefix_payload:
                await self.start_activity(
                    current_call_sid=current_call_sid,
                    now_ts=now_ts,
                    mode="normal_after_playback",
                    threshold=self.controller.start_rms,
                    raw_rms=decoded_audio.rms,
                    conditioned_rms=decoded_audio.conditioned_rms,
                    prefix_payload=prefix_payload,
                )
            return

        await self.live_input.queue_pcm16k_payload(decoded_audio.pcm16k)
        observation = self.controller.observe_active_frame(
            now_ts=now_ts,
            raw_rms=decoded_audio.rms,
            conditioned_rms=decoded_audio.conditioned_rms,
        )
        if observation.silence_reset_ms is not None:
            await self.append_activity_trace(
                current_call_sid=current_call_sid,
                event_type="manual_activity_silence_reset",
                reason="voice_energy_resumed_before_timeout",
                now_ts=now_ts,
                silence_ms=observation.silence_reset_ms,
            )
        if observation.progress_due:
            await self.append_activity_trace(
                current_call_sid=current_call_sid,
                event_type="manual_activity_progress",
                reason="awaiting_end_boundary",
                now_ts=now_ts,
            )
        if observation.end_due:
            await self.send_end(
                current_call_sid=current_call_sid,
                reason="silence_timeout",
                silence_ms=observation.silence_ms,
            )
