"""
Mutable runtime state for a single Twilio Media Streams bridge session.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TwilioMediaStreamState:
    assistant_speaking: bool = False
    assistant_last_output_at: float | None = None
    media_frames: int = 0
    last_media_stats_at: float = 0.0
    decode_fail_count: int = 0
    last_decode_error_at: float = 0.0
    logged_non_inbound_track: bool = False
    last_completed_assistant_text: str | None = None
    close_after_turn_complete: bool = False
    assistant_playback_pending: bool = False
    pending_playback_mark: str | None = None
    outbound_mark_counter: int = 0
    model_turn_sent_audio: bool = False
    live_setup_complete: bool = False
    opening_turn_sent: bool = False
    opening_turn_playback_complete: bool = False
    opening_turn_audio_started: bool = False
    opening_interrupt_guard_until: float = 0.0

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

    def mark_live_setup_complete(self) -> None:
        self.live_setup_complete = True

    def start_opening_turn(self, *, guard_seconds: float) -> None:
        self.opening_turn_sent = True
        self.opening_turn_playback_complete = False
        self.opening_turn_audio_started = False
        self.opening_interrupt_guard_until = time.monotonic() + max(0.0, guard_seconds)

    def note_opening_audio_started(self) -> None:
        if self.opening_turn_sent and not self.opening_turn_playback_complete:
            self.opening_turn_audio_started = True

    def complete_opening_turn(self) -> None:
        if self.opening_turn_sent:
            self.opening_turn_playback_complete = True
            self.opening_interrupt_guard_until = 0.0

    def cancel_opening_turn(self) -> None:
        self.opening_turn_sent = False
        self.opening_turn_playback_complete = False
        self.opening_turn_audio_started = False
        self.opening_interrupt_guard_until = 0.0

    def should_guard_interrupt(self, *, now: float) -> bool:
        if not self.opening_turn_sent or self.opening_turn_playback_complete:
            return False
        return now < self.opening_interrupt_guard_until

    def confirm_playback_mark(self, mark_name: str) -> bool:
        if not self.pending_playback_mark or mark_name != self.pending_playback_mark:
            return False
        self.pending_playback_mark = None
        self.assistant_playback_pending = False
        self.assistant_speaking = False
        if self.opening_turn_sent and not self.opening_turn_playback_complete:
            self.complete_opening_turn()
        return True

    def mark_model_audio_sent(self) -> None:
        self.model_turn_sent_audio = True
        self.assistant_playback_pending = True

    def finalize_turn_playback_state(self, *, now: float) -> None:
        self.assistant_playback_pending = self.pending_playback_mark is not None
        self.assistant_speaking = False
        self.assistant_last_output_at = now
        self.model_turn_sent_audio = False

    def interrupt(self, *, now: float) -> None:
        self.assistant_speaking = False
        self.assistant_playback_pending = False
        self.pending_playback_mark = None
        self.assistant_last_output_at = now
