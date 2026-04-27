from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ManualActivityFrameObservation:
    silence_reset_ms: int | None = None
    progress_due: bool = False
    end_due: bool = False
    silence_ms: int = 0


@dataclass(slots=True)
class TwilioManualActivityController:
    frame_ms: int
    prefix_padding_ms: int
    start_rms: int
    end_rms: int
    start_hits_required: int
    barge_rms: int
    barge_hits_required: int
    silence_hits_required: int
    silence_reset_trace_ms: int
    progress_trace_interval_seconds: float
    activity_active: bool = False
    activity_hits: int = 0
    silence_hits: int = 0
    activity_started_at: float = 0.0
    activity_last_trace_at: float = 0.0
    activity_peak_raw_rms: int = 0
    activity_lowest_conditioned_rms: int = 0
    activity_last_raw_rms: int = 0
    activity_last_conditioned_rms: int = 0
    _prefix_frames: deque[bytes] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        max_prefix_frames = max(1, int(self.prefix_padding_ms / max(self.frame_ms, 1)))
        self._prefix_frames = deque(maxlen=max_prefix_frames)

    @property
    def active(self) -> bool:
        return self.activity_active

    @property
    def silence_target_ms(self) -> int:
        return self.silence_hits_required * self.frame_ms

    def reset_runtime_stats(self) -> None:
        self.activity_started_at = 0.0
        self.activity_last_trace_at = 0.0
        self.activity_peak_raw_rms = 0
        self.activity_lowest_conditioned_rms = 0
        self.activity_last_raw_rms = 0
        self.activity_last_conditioned_rms = 0

    def reset_all(self) -> None:
        self.activity_active = False
        self.activity_hits = 0
        self.silence_hits = 0
        self._prefix_frames.clear()
        self.reset_runtime_stats()

    def drop_while_playing(self) -> None:
        self.activity_hits = 0
        self.silence_hits = 0
        if not self.activity_active:
            self._prefix_frames.clear()
            self.reset_runtime_stats()

    def observe_normal_start_candidate(self, *, pcm16k: bytes, raw_rms: int) -> bytes | None:
        return self._observe_start_candidate(
            pcm16k=pcm16k,
            raw_rms=raw_rms,
            threshold=self.start_rms,
            hits_required=self.start_hits_required,
        )

    def observe_barge_in_candidate(self, *, pcm16k: bytes, raw_rms: int) -> bytes | None:
        return self._observe_start_candidate(
            pcm16k=pcm16k,
            raw_rms=raw_rms,
            threshold=self.barge_rms,
            hits_required=self.barge_hits_required,
        )

    def begin_activity(self, *, now_ts: float, raw_rms: int, conditioned_rms: int) -> None:
        self.activity_active = True
        self.activity_hits = 0
        self.silence_hits = 0
        self.activity_started_at = now_ts
        self.activity_last_trace_at = now_ts
        self.activity_peak_raw_rms = max(0, int(raw_rms))
        self.activity_lowest_conditioned_rms = max(0, int(conditioned_rms))
        self.activity_last_raw_rms = max(0, int(raw_rms))
        self.activity_last_conditioned_rms = max(0, int(conditioned_rms))

    def observe_active_frame(
        self,
        *,
        now_ts: float,
        raw_rms: int,
        conditioned_rms: int,
    ) -> ManualActivityFrameObservation:
        self._record_activity_frame(
            now_ts=now_ts,
            raw_rms=raw_rms,
            conditioned_rms=conditioned_rms,
        )
        silence_reset_ms: int | None = None
        if conditioned_rms >= self.end_rms:
            silence_ms_before_reset = self.silence_hits * self.frame_ms
            if (
                self.silence_hits > 0
                and silence_ms_before_reset >= self.silence_reset_trace_ms
            ):
                silence_reset_ms = silence_ms_before_reset
            self.silence_hits = 0
        else:
            self.silence_hits += 1

        progress_due = False
        if (now_ts - self.activity_last_trace_at) >= self.progress_trace_interval_seconds:
            self.activity_last_trace_at = now_ts
            progress_due = True

        silence_ms = self.silence_hits * self.frame_ms
        end_due = self.silence_hits >= self.silence_hits_required
        return ManualActivityFrameObservation(
            silence_reset_ms=silence_reset_ms,
            progress_due=progress_due,
            end_due=end_due,
            silence_ms=silence_ms,
        )

    def activity_elapsed_ms(self, *, now_ts: float | None = None) -> int:
        if self.activity_started_at <= 0.0:
            return 0
        current_ts = time.monotonic() if now_ts is None else now_ts
        return max(0, int((current_ts - self.activity_started_at) * 1000))

    def build_trace_text(
        self,
        *,
        reason: str,
        now_ts: float | None = None,
        silence_ms: int | None = None,
    ) -> str | None:
        if self.activity_started_at <= 0.0:
            return None
        resolved_now = time.monotonic() if now_ts is None else now_ts
        resolved_silence_ms = self.silence_hits * self.frame_ms if silence_ms is None else max(0, silence_ms)
        return (
            f"reason={reason} elapsed_ms={self.activity_elapsed_ms(now_ts=resolved_now)} "
            f"silence_ms={resolved_silence_ms} silence_target_ms={self.silence_target_ms} "
            f"last_raw_rms={self.activity_last_raw_rms} "
            f"last_conditioned_rms={self.activity_last_conditioned_rms} "
            f"peak_raw_rms={self.activity_peak_raw_rms} "
            f"lowest_conditioned_rms={self.activity_lowest_conditioned_rms} "
            f"end_rms={self.end_rms}"
        )

    def _observe_start_candidate(
        self,
        *,
        pcm16k: bytes,
        raw_rms: int,
        threshold: int,
        hits_required: int,
    ) -> bytes | None:
        self._prefix_frames.append(pcm16k)
        if raw_rms >= threshold:
            self.activity_hits += 1
        else:
            self.activity_hits = 0
            self._prefix_frames.clear()
            return None

        if self.activity_hits < hits_required:
            return None

        prefix_payload = b"".join(self._prefix_frames)
        self._prefix_frames.clear()
        return prefix_payload

    def _record_activity_frame(
        self,
        *,
        now_ts: float,
        raw_rms: int,
        conditioned_rms: int,
    ) -> None:
        if self.activity_started_at <= 0.0:
            self.activity_started_at = now_ts
        self.activity_last_raw_rms = max(0, int(raw_rms))
        self.activity_last_conditioned_rms = max(0, int(conditioned_rms))
        self.activity_peak_raw_rms = max(self.activity_peak_raw_rms, self.activity_last_raw_rms)
        if self.activity_lowest_conditioned_rms == 0:
            self.activity_lowest_conditioned_rms = self.activity_last_conditioned_rms
        else:
            self.activity_lowest_conditioned_rms = min(
                self.activity_lowest_conditioned_rms,
                self.activity_last_conditioned_rms,
            )
