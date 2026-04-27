from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.twilio.media_stream_state import TwilioMediaStreamState

AppendTraceCallback = Callable[..., Awaitable[None]]
FinalizeBoundCallCallback = Callable[..., Awaitable[None]]
CloseWebSocketCallback = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class TwilioBusinessCloseService:
    state: TwilioMediaStreamState
    append_trace: AppendTraceCallback
    finalize_bound_call: FinalizeBoundCallCallback
    close_websocket: CloseWebSocketCallback
    stream_done: asyncio.Event

    def register_completed_assistant_reply(
        self,
        *,
        text: str,
        should_close_after_playback: bool,
    ) -> None:
        self.state.last_completed_assistant_text = text
        self.state.close_after_turn_complete = should_close_after_playback

    async def maybe_close_after_playback(self, *, current_call_sid: str | None) -> bool:
        if not self.state.close_after_turn_complete:
            return False
        self.state.close_after_turn_complete = False
        await self.append_trace(
            current_call_sid,
            event_type="auto_finalize_triggered",
            text=self.state.last_completed_assistant_text,
            level="success",
        )
        await self.finalize_bound_call(trigger="closing_phrase", run_extraction=True)
        self.stream_done.set()
        try:
            await self.close_websocket()
        except Exception:
            pass
        return True
