import logging
from dataclasses import dataclass

from app.core.database import AsyncSessionLocal
from app.repositories.call_repository import CallRepository
from app.services.twilio.prompt_runtime_helpers import _build_test_session_service
from app.services.twilio.trace_store import _append_call_trace
from app.services.twilio_voice_agent_service import twilio_voice_agent_service

logger = logging.getLogger(__name__)

TERMINAL_CALL_STATUSES = {"completed", "canceled", "failed", "busy", "no-answer"}


@dataclass(frozen=True)
class TwilioStreamStatusPayload:
    account_sid: str | None = None
    call_sid: str | None = None
    stream_sid: str | None = None
    stream_name: str | None = None
    stream_event: str | None = None
    stream_error: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class TwilioVoiceStatusPayload:
    call_sid: str | None = None
    call_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    to_number: str | None = None
    from_number: str | None = None
    duration: str | None = None


class TwilioStatusService:
    async def handle_stream_status(self, payload: TwilioStreamStatusPayload) -> dict:
        stream_event = (payload.stream_event or "").strip() or "-"
        stream_error = (payload.stream_error or "").strip()
        level = "info"
        if stream_event == "stream-started":
            level = "success"
        elif stream_event == "stream-stopped":
            level = "warning"
        elif stream_event == "stream-error":
            level = "error"

        await _append_call_trace(
            (payload.call_sid or "").strip() or None,
            event_type="media_stream_status",
            text=(
                f"event={stream_event} stream_sid={(payload.stream_sid or '').strip() or '-'} "
                f"stream_name={(payload.stream_name or '').strip() or '-'} "
                f"timestamp={(payload.timestamp or '').strip() or '-'} "
                f"account_sid={(payload.account_sid or '').strip() or '-'}"
                + (f" error={stream_error}" if stream_error else "")
            ),
            level=level,
        )
        return {"ok": True}

    async def handle_voice_status(self, payload: TwilioVoiceStatusPayload) -> dict:
        call_sid = (payload.call_sid or "").strip()
        normalized_status = (payload.call_status or "").strip().lower()
        if normalized_status in TERMINAL_CALL_STATUSES:
            await twilio_voice_agent_service.clear_session(call_sid)
            if call_sid:
                await self._finalize_bound_test_session(call_sid)

        if call_sid and (
            (payload.error_code or "").strip() or (payload.error_message or "").strip()
        ):
            await _append_call_trace(
                call_sid,
                event_type="call_status_error",
                text=(
                    f"code={(payload.error_code or '').strip() or '-'} "
                    f"message={(payload.error_message or '').strip() or '-'}"
                ),
                level="error",
            )

        logger.info(
            "Twilio status callback. CallSid=%s status=%s From=%s To=%s Duration=%s ErrorCode=%s ErrorMessage=%s",
            payload.call_sid,
            payload.call_status,
            payload.from_number,
            payload.to_number,
            payload.duration,
            payload.error_code,
            payload.error_message,
        )
        return {
            "call_sid": payload.call_sid,
            "status": payload.call_status,
            "error_code": payload.error_code,
            "error_message": payload.error_message,
            "from": payload.from_number,
            "to": payload.to_number,
            "duration": payload.duration,
        }

    async def _finalize_bound_test_session(self, call_sid: str) -> None:
        try:
            async with AsyncSessionLocal() as db:
                call_repo = CallRepository(db)
                existing_call = await call_repo.get_by_sip_call_id(call_sid)
                if existing_call:
                    service = _build_test_session_service(db)
                    await service.finalize_test_session(
                        call_id=existing_call.id,
                        template_code=(existing_call.extra_data or {}).get("template_code"),
                        run_extraction=True,
                    )
        except Exception as exc:
            logger.warning(
                "Failed to finalize Twilio call on status callback. call_sid=%s error=%s",
                call_sid,
                exc,
            )
