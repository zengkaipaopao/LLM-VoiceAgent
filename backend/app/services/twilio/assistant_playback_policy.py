from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.media_stream_state import TwilioMediaStreamState
from app.services.twilio.twilio_playback_adapter import TwilioPlaybackAdapter

AppendTraceCallback = Callable[..., Awaitable[None]]
CloseAfterPlaybackCallback = Callable[[], Awaitable[bool]]


@dataclass(slots=True)
class AssistantPlaybackPolicyService:
    state: TwilioMediaStreamState
    codec: TwilioMediaAudioCodec
    playback: TwilioPlaybackAdapter
    append_trace: AppendTraceCallback
    assistant_turn_locally_interrupted: bool = False
    assistant_audio_drop_trace_emitted: bool = False

    async def handle_playback_mark(
        self,
        *,
        current_call_sid: str | None,
        mark_name: str,
        arm_followup_probe: Callable[[str], Awaitable[None]],
        close_after_playback_if_needed: CloseAfterPlaybackCallback,
    ) -> bool:
        if mark_name:
            await self.append_trace(
                current_call_sid,
                event_type="playback_mark",
                text=mark_name,
                level="info",
            )
        if not self.state.confirm_playback_mark(mark_name):
            return False
        await self.append_trace(
            current_call_sid,
            event_type="playback_complete",
            text=mark_name or "assistant_audio",
            level="success",
        )
        if await close_after_playback_if_needed():
            return True
        await arm_followup_probe(mark_name or "assistant_audio")
        return True

    async def handle_model_interrupted(
        self,
        *,
        current_call_sid: str | None,
    ) -> None:
        if not self.playback.active:
            return
        self.state.interrupt(
            now=time.monotonic(),
            preserve_pending_mark=bool(self.state.pending_playback_mark),
        )
        self.codec.clear_outbound_audio()
        await self.playback.send_clear()
        await self.append_trace(
            current_call_sid,
            event_type="interrupted",
            text="Model response interrupted by activity.",
            level="warning",
        )
        self.assistant_turn_locally_interrupted = False
        self.assistant_audio_drop_trace_emitted = False

    async def should_drop_assistant_audio(
        self,
        *,
        current_call_sid: str | None,
    ) -> bool:
        if self.assistant_turn_locally_interrupted:
            if not self.assistant_audio_drop_trace_emitted:
                self.assistant_audio_drop_trace_emitted = True
                await self.append_trace(
                    current_call_sid,
                    event_type="assistant_audio_dropped_after_local_barge_in",
                    text="Dropping remaining assistant audio for interrupted turn.",
                    level="warning",
                )
            return True
        return False

    async def handle_assistant_audio(
        self,
        *,
        current_call_sid: str | None,
        mime_type: str | None,
        pcm_bytes: bytes,
    ) -> None:
        if not self.state.model_turn_sent_audio:
            self.assistant_audio_drop_trace_emitted = False
        self.state.note_assistant_activity(now=time.monotonic(), speaking=True)
        if not self.state.model_turn_sent_audio:
            await self.append_trace(
                current_call_sid,
                event_type="assistant_audio_started",
                text=mime_type or "audio/pcm",
                level="success",
            )
        try:
            frames = self.codec.encode_model_audio(pcm_bytes, mime_type=mime_type)
        except Exception as exc:
            await self.append_trace(
                current_call_sid,
                event_type="assistant_audio_encode_error",
                text=str(exc),
                level="warning",
            )
            return

        if not self.playback.active:
            return

        if not frames:
            await self.append_trace(
                current_call_sid,
                event_type="assistant_audio_empty",
                text=(
                    f"mime_type={mime_type or 'audio/pcm'} "
                    f"source_bytes={len(pcm_bytes)}"
                ),
                level="warning",
            )
            return

        await self.append_trace(
            current_call_sid,
            event_type="assistant_audio_forwarded",
            text=(
                f"mime_type={mime_type or 'audio/pcm'} "
                f"source_bytes={len(pcm_bytes)} frames={len(frames)} "
                f"payload_bytes={sum(len(frame) for frame in frames)}"
            ),
            level="info",
        )
        self.state.mark_model_audio_sent()
        await self.playback.send_media_frames(frames)

    async def handle_turn_complete(
        self,
        *,
        current_call_sid: str | None,
        reason: str,
        close_after_playback_if_needed: CloseAfterPlaybackCallback,
    ) -> bool:
        turn_completed_after_local_barge_in = self.assistant_turn_locally_interrupted
        if self.playback.active and not turn_completed_after_local_barge_in:
            tail_frames = self.codec.flush_outbound_audio(pad_to_frame=True)
            if tail_frames:
                await self.append_trace(
                    current_call_sid,
                    event_type="assistant_audio_tail_flushed",
                    text=(
                        f"frames={len(tail_frames)} "
                        f"payload_bytes={sum(len(frame) for frame in tail_frames)}"
                    ),
                    level="info",
                )
                self.state.mark_model_audio_sent()
                await self.playback.send_media_frames(tail_frames)
        if (
            self.playback.active
            and not turn_completed_after_local_barge_in
            and self.state.model_turn_sent_audio
            and not self.state.pending_playback_mark
        ):
            playback_mark = self.state.next_playback_mark()
            await self.playback.send_mark(playback_mark)
            await self.append_trace(
                current_call_sid,
                event_type="playback_mark_sent",
                text=playback_mark,
                level="info",
        )
        if turn_completed_after_local_barge_in:
            self.assistant_turn_locally_interrupted = False
            self.assistant_audio_drop_trace_emitted = False
        await self.append_trace(
            current_call_sid,
            event_type="turn_complete",
            text=f"reason={reason}",
            level="info",
        )
        if not self.state.model_turn_sent_audio:
            await self.append_trace(
                current_call_sid,
                event_type="assistant_turn_without_audio",
                text="Gemini Live completed a turn without emitting audio parts.",
                level="warning",
            )
        self.state.finalize_turn_playback_state(now=time.monotonic())
        return await close_after_playback_if_needed()
