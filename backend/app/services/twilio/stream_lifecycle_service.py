from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.twilio.media_stream_observer_bridge_service import (
    TwilioMediaStreamObserverBridgeService,
)

AppendTraceCallback = Callable[..., Awaitable[None]]
FinalizeBoundCallCallback = Callable[..., Awaitable[None]]
MarkStreamInactiveCallback = Callable[[str | None], Awaitable[None]]
CloseWebSocketCallback = Callable[[], Awaitable[None]]
CloseRealtimeAudioInputCallback = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class TwilioStreamLifecycleService:
    observer: TwilioMediaStreamObserverBridgeService
    append_trace: AppendTraceCallback
    finalize_bound_call: FinalizeBoundCallCallback
    mark_stream_inactive: MarkStreamInactiveCallback
    close_websocket: CloseWebSocketCallback
    stream_done: asyncio.Event

    async def handle_stream_stop(
        self,
        *,
        current_call_sid: str | None,
        close_realtime_audio_input: CloseRealtimeAudioInputCallback,
    ) -> None:
        self.stream_done.set()
        try:
            await close_realtime_audio_input()
        except Exception:
            pass
        await self.append_trace(current_call_sid, event_type="stream_stop", level="info")
        await self._cleanup_core(
            current_call_sid=current_call_sid,
            reason="stream_stop",
            persist_trigger="stream_stop",
            finalize=True,
        )

    async def handle_websocket_disconnect(
        self,
        *,
        current_call_sid: str | None,
    ) -> None:
        self.stream_done.set()
        await self.append_trace(current_call_sid, event_type="stream_disconnect", level="warning")
        await self._cleanup_core(
            current_call_sid=current_call_sid,
            reason="websocket_disconnect",
            persist_trigger="websocket_disconnect",
            finalize=True,
        )

    async def handle_stream_error(
        self,
        *,
        current_call_sid: str | None,
        error_text: str,
    ) -> None:
        self.stream_done.set()
        await self.append_trace(
            current_call_sid,
            event_type="stream_error",
            text=error_text,
            level="error",
        )
        await self._cleanup_core(
            current_call_sid=current_call_sid,
            reason="stream_error",
            persist_trigger="stream_error",
            finalize=True,
        )

    async def handle_finally(
        self,
        *,
        current_call_sid: str | None,
    ) -> None:
        self.stream_done.set()
        await self._cleanup_core(
            current_call_sid=current_call_sid,
            reason="stream_finally",
            persist_trigger="stream_finally",
            finalize=False,
        )
        try:
            await self.close_websocket()
        except Exception:
            pass

    async def _cleanup_core(
        self,
        *,
        current_call_sid: str | None,
        reason: str,
        persist_trigger: str,
        finalize: bool,
    ) -> None:
        await self.observer.disarm_followup_probe(
            reason=reason,
        )
        await self.observer.persist_inbound_debug_wav(trigger=persist_trigger)
        if finalize:
            try:
                await self.finalize_bound_call(trigger=reason, run_extraction=True)
            except Exception:
                pass
        await self.mark_stream_inactive(current_call_sid)
