"""
Mutable runtime state for a single Twilio Media Streams bridge session.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TwilioMediaStreamState:
    pre_roll_frame_limit: int
    adaptive_threshold_floor: int
    rms_window_limit: int = 80
    in_resample_state: tuple[object, object] | None = None
    out_resample_state: tuple[object, object] | None = None
    assistant_speaking: bool = False
    assistant_last_output_at: float | None = None
    opening_suppress_until: float | None = None
    speaking_active: bool = False
    silence_started_at: float | None = None
    last_voice_at: float | None = None
    turn_started_at: float | None = None
    awaiting_model_response: bool = False
    awaiting_model_since: float | None = None
    awaiting_model_retry_count: int = 0
    awaiting_manual_turn: bool = False
    manual_inject_lock_until: float | None = None
    voice_frame_streak: int = 0
    adaptive_threshold: int = field(init=False)
    media_frames: int = 0
    last_media_stats_at: float = 0.0
    decode_fail_count: int = 0
    last_decode_error_at: float = 0.0
    logged_non_inbound_track: bool = False
    last_completed_assistant_text: str | None = None
    close_after_turn_complete: bool = False
    manual_activity_started: bool = False
    assistant_playback_pending: bool = False
    pending_playback_mark: str | None = None
    outbound_mark_counter: int = 0
    model_turn_sent_audio: bool = False
    pre_roll_frames: deque[bytes] = field(init=False)
    rms_window: deque[int] = field(init=False)

    def __post_init__(self) -> None:
        self.pre_roll_frames = deque(maxlen=self.pre_roll_frame_limit)
        self.rms_window = deque(maxlen=self.rms_window_limit)
        self.adaptive_threshold = self.adaptive_threshold_floor

    def begin_opening_suppression(self, *, now: float, duration_ms: int) -> None:
        self.opening_suppress_until = now + (duration_ms / 1000.0)

    def clear_opening_suppression(self) -> None:
        self.opening_suppress_until = None

    def opening_suppressed(self, now: float) -> bool:
        return self.opening_suppress_until is not None and now < self.opening_suppress_until

    def start_waiting_for_model(self, *, now: float, manual_turn: bool) -> None:
        self.awaiting_model_response = True
        self.awaiting_model_since = now
        self.awaiting_model_retry_count = 0
        self.awaiting_manual_turn = manual_turn

    def clear_waiting_for_model(self) -> None:
        self.awaiting_model_response = False
        self.awaiting_model_since = None
        self.awaiting_model_retry_count = 0
        self.awaiting_manual_turn = False

    def begin_manual_lock(self, *, now: float, seconds: float) -> None:
        self.manual_inject_lock_until = now + seconds

    def manual_lock_active(self, now: float) -> bool:
        return self.manual_inject_lock_until is not None and now < self.manual_inject_lock_until

    def clear_voice_detection_window(self) -> None:
        self.voice_frame_streak = 0
        self.pre_roll_frames.clear()

    def reset_turn_detection(self) -> None:
        self.speaking_active = False
        self.turn_started_at = None
        self.silence_started_at = None
        self.clear_voice_detection_window()

    def note_assistant_activity(self, *, now: float, speaking: bool) -> None:
        self.assistant_last_output_at = now
        if speaking:
            self.assistant_speaking = True

    def next_playback_mark(self) -> str:
        self.outbound_mark_counter += 1
        mark_name = f"assistant-turn-{self.outbound_mark_counter}"
        self.pending_playback_mark = mark_name
        self.assistant_playback_pending = True
        return mark_name

    def confirm_playback_mark(self, mark_name: str) -> bool:
        if not self.pending_playback_mark or mark_name != self.pending_playback_mark:
            return False
        self.pending_playback_mark = None
        self.assistant_playback_pending = False
        self.assistant_speaking = False
        return True

    def mark_model_audio_sent(self) -> None:
        self.model_turn_sent_audio = True
        self.assistant_playback_pending = True

    def finalize_turn_playback_state(self, *, now: float) -> None:
        self.assistant_playback_pending = self.pending_playback_mark is not None
        self.assistant_speaking = False
        self.assistant_last_output_at = now
        self.clear_waiting_for_model()
        self.model_turn_sent_audio = False

    def interrupt(self, *, now: float) -> None:
        self.assistant_speaking = False
        self.assistant_playback_pending = False
        self.pending_playback_mark = None
        self.assistant_last_output_at = now
        self.clear_waiting_for_model()
        self.clear_opening_suppression()
