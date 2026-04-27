from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.twilio.media_stream_observer import TwilioMediaStreamObserver

AppendTraceCallback = Callable[..., Awaitable[None]]
AppendManualActivityTraceCallback = Callable[..., Awaitable[None]]
ManualActivityActiveGetter = Callable[[], bool]


@dataclass(slots=True)
class TwilioMediaStreamObserverBridgeService:
    observer: TwilioMediaStreamObserver
    append_trace: AppendTraceCallback
    append_manual_activity_trace: AppendManualActivityTraceCallback
    manual_activity_control: bool
    manual_activity_active_getter: ManualActivityActiveGetter

    @property
    def followup_probe_armed(self) -> bool:
        return self.observer.followup_probe_armed

    def bind_call_sid(self, call_sid: str | None) -> None:
        self.observer.bind_call_sid(call_sid)

    def append_inbound_audio(self, *, pcm8k: bytes, pcm16k: bytes) -> None:
        self.observer.append_inbound_audio(pcm8k=pcm8k, pcm16k=pcm16k)

    def note_followup_transcript_observed(self) -> None:
        self.observer.note_followup_transcript_observed()

    async def arm_followup_probe(self, trigger: str) -> None:
        await self.observer.arm_followup_probe(
            trigger=trigger,
            append_trace=self.append_trace,
        )

    async def disarm_followup_probe(self, reason: str) -> None:
        await self.observer.disarm_followup_probe(
            reason=reason,
            append_trace=self.append_trace,
            append_manual_activity_trace=self.append_manual_activity_trace,
            manual_activity_control=self.manual_activity_control,
            manual_activity_active=self.manual_activity_active_getter(),
        )

    async def observe_followup_audio(
        self,
        *,
        now_ts: float,
        rms: int,
        pcm8k: bytes,
        pcm16k: bytes,
    ) -> None:
        await self.observer.observe_followup_audio(
            now_ts=now_ts,
            rms=rms,
            pcm8k=pcm8k,
            pcm16k=pcm16k,
            append_trace=self.append_trace,
            append_manual_activity_trace=self.append_manual_activity_trace,
            manual_activity_control=self.manual_activity_control,
            manual_activity_active=self.manual_activity_active_getter(),
        )

    async def persist_inbound_debug_wav(self, trigger: str) -> None:
        await self.observer.persist_inbound_debug_wav(
            trigger=trigger,
            append_trace=self.append_trace,
        )
