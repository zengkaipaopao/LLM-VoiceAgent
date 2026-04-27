from __future__ import annotations

import pytest

from app.services.twilio.media_stream_observer_bridge_service import (
    TwilioMediaStreamObserverBridgeService,
)


class _DummyObserver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.followup_probe_armed = False
        self.bound_call_sid: str | None = None
        self.inbound_audio: list[tuple[bytes, bytes]] = []
        self.transcript_observed = False

    def bind_call_sid(self, call_sid: str | None) -> None:
        self.bound_call_sid = call_sid

    def append_inbound_audio(self, *, pcm8k: bytes, pcm16k: bytes) -> None:
        self.inbound_audio.append((pcm8k, pcm16k))

    def note_followup_transcript_observed(self) -> None:
        self.transcript_observed = True

    async def arm_followup_probe(self, **kwargs) -> None:
        self.followup_probe_armed = True
        self.calls.append(("arm", kwargs))

    async def disarm_followup_probe(self, **kwargs) -> None:
        self.calls.append(("disarm", kwargs))

    async def observe_followup_audio(self, **kwargs) -> None:
        self.calls.append(("observe", kwargs))

    async def persist_inbound_debug_wav(self, **kwargs) -> None:
        self.calls.append(("persist", kwargs))


@pytest.mark.asyncio
async def test_observer_bridge_forwards_manual_activity_state_and_trace_callbacks():
    observer = _DummyObserver()

    async def append_trace(*args, **kwargs):
        return None

    async def append_manual_activity_trace(**kwargs):
        return None

    service = TwilioMediaStreamObserverBridgeService(
        observer=observer,
        append_trace=append_trace,
        append_manual_activity_trace=append_manual_activity_trace,
        manual_activity_control=True,
        manual_activity_active_getter=lambda: True,
    )

    service.bind_call_sid("CA123")
    service.append_inbound_audio(pcm8k=b"12", pcm16k=b"34")
    service.note_followup_transcript_observed()
    await service.arm_followup_probe("assistant-turn-1")
    await service.observe_followup_audio(
        now_ts=1.0,
        rms=180,
        pcm8k=b"56",
        pcm16k=b"78",
    )
    await service.disarm_followup_probe("input_transcript_finished")
    await service.persist_inbound_debug_wav("stream_stop")

    assert observer.bound_call_sid == "CA123"
    assert observer.inbound_audio == [(b"12", b"34")]
    assert observer.transcript_observed is True
    assert observer.calls[0][0] == "arm"
    assert observer.calls[1][0] == "observe"
    assert observer.calls[1][1]["manual_activity_active"] is True
    assert observer.calls[2][0] == "disarm"
    assert observer.calls[2][1]["manual_activity_control"] is True
    assert observer.calls[2][1]["manual_activity_active"] is True
    assert observer.calls[3] == ("persist", {"trigger": "stream_stop", "append_trace": append_trace})
