"""
Mutable runtime state for a single Twilio Media Streams bridge session.
"""
from __future__ import annotations

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
        self.model_turn_sent_audio = False

    def interrupt(self, *, now: float, preserve_pending_mark: bool = False) -> None:
        self.assistant_speaking = False
        if preserve_pending_mark:
            self.assistant_playback_pending = self.pending_playback_mark is not None
        else:
            self.assistant_playback_pending = False
            self.pending_playback_mark = None
        self.assistant_last_output_at = now
        self.model_turn_sent_audio = False
