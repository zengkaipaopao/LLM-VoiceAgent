from __future__ import annotations

import pytest

from app.services.twilio.debug_audio_capture import RollingPcmCapture
from app.services.twilio.media_stream_observer import TwilioMediaStreamObserver


def _build_capture(*, sample_rate: int, artifact_key: str, duration_seconds: int = 1) -> RollingPcmCapture:
    return RollingPcmCapture(
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        artifact_key=artifact_key,
    )


@pytest.mark.asyncio
async def test_observer_persists_followup_debug_audio_and_marks_stalled(tmp_path):
    trace_events: list[tuple[str, str, str]] = []
    manual_events: list[tuple[str, str, str]] = []

    async def append_trace(call_sid: str, *, event_type: str, text: str, level: str) -> None:
        trace_events.append((event_type, text, level))

    async def append_manual_activity_trace(*, event_type: str, reason: str, level: str = "info") -> None:
        manual_events.append((event_type, reason, level))

    observer = TwilioMediaStreamObserver(
        call_sid="CA-followup",
        debug_wav_enabled=True,
        debug_output_dir=str(tmp_path),
        followup_capture_seconds=5,
        followup_rms_threshold=100,
        followup_min_hits=1,
        inbound_debug_captures={
            "pcm8k_raw": _build_capture(sample_rate=8000, artifact_key="inbound-8k"),
            "pcm16k_resampled": _build_capture(sample_rate=16000, artifact_key="inbound-16k"),
        },
        followup_debug_captures={
            "followup_pcm8k_raw": _build_capture(
                sample_rate=100,
                artifact_key="followup-8k",
            ),
            "followup_pcm16k_resampled": _build_capture(
                sample_rate=100,
                artifact_key="followup-16k",
            ),
        },
    )

    await observer.arm_followup_probe(trigger="assistant-turn-1", append_trace=append_trace)
    await observer.observe_followup_audio(
        now_ts=12.0,
        rms=120,
        pcm8k=b"\x00\x01" * 100,
        pcm16k=b"\x00\x01" * 100,
        append_trace=append_trace,
        append_manual_activity_trace=append_manual_activity_trace,
        manual_activity_control=True,
        manual_activity_active=True,
    )

    event_types = [event_type for event_type, _, _ in trace_events]
    assert "followup_probe_armed" in event_types
    assert "followup_probe_speech_detected" in event_types
    assert "followup_debug_wav_saved" in event_types
    assert "gemini_turn_detection_stalled" in event_types
    assert manual_events == [
        ("manual_activity_end_overdue", "followup_probe_full_no_input_transcript", "warning")
    ]


@pytest.mark.asyncio
async def test_observer_persists_inbound_debug_audio_once(tmp_path):
    trace_events: list[tuple[str, str, str]] = []

    async def append_trace(call_sid: str, *, event_type: str, text: str, level: str) -> None:
        trace_events.append((event_type, text, level))

    observer = TwilioMediaStreamObserver(
        call_sid="CA-inbound",
        debug_wav_enabled=True,
        debug_output_dir=str(tmp_path),
        followup_capture_seconds=5,
        followup_rms_threshold=100,
        followup_min_hits=2,
        inbound_debug_captures={
            "pcm8k_raw": _build_capture(sample_rate=100, artifact_key="inbound-8k"),
            "pcm16k_resampled": _build_capture(sample_rate=100, artifact_key="inbound-16k"),
        },
        followup_debug_captures={},
    )
    observer.append_inbound_audio(
        pcm8k=b"\x00\x01" * 100,
        pcm16k=b"\x00\x01" * 100,
    )

    await observer.persist_inbound_debug_wav(trigger="stream_stop", append_trace=append_trace)
    await observer.persist_inbound_debug_wav(trigger="stream_finally", append_trace=append_trace)

    saved_events = [item for item in trace_events if item[0] == "inbound_debug_wav_saved"]
    assert len(saved_events) == 1
    assert "trigger=stream_stop" in saved_events[0][1]
