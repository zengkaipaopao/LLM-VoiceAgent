import logging
from typing import Optional

from fastapi import APIRouter, Form, Request

from app.core.database import AsyncSessionLocal
from app.repositories.call_repository import CallRepository
from app.schemas.base import ResponseBase
from app.services.twilio.prompt_runtime_helpers import _build_test_session_service
from app.services.twilio.trace_store import _append_call_trace
from app.services.twilio.webhook_verification import _verify_webhook_or_raise
from app.services.twilio_voice_agent_service import twilio_voice_agent_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/voice/stream/status",
    response_model=ResponseBase[dict],
    name="twilio_voice_stream_status_callback",
)
async def twilio_voice_stream_status_callback(
    request: Request,
    AccountSid: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    StreamSid: Optional[str] = Form(None),  # noqa: N803
    StreamName: Optional[str] = Form(None),  # noqa: N803
    StreamEvent: Optional[str] = Form(None),  # noqa: N803
    StreamError: Optional[str] = Form(None),  # noqa: N803
    Timestamp: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)

    stream_event = (StreamEvent or "").strip() or "-"
    stream_error = (StreamError or "").strip()
    level = "info"
    if stream_event == "stream-started":
        level = "success"
    elif stream_event == "stream-stopped":
        level = "warning"
    elif stream_event == "stream-error":
        level = "error"

    await _append_call_trace(
        (CallSid or "").strip() or None,
        event_type="media_stream_status",
        text=(
            f"event={stream_event} stream_sid={(StreamSid or '').strip() or '-'} "
            f"stream_name={(StreamName or '').strip() or '-'} "
            f"timestamp={(Timestamp or '').strip() or '-'} "
            f"account_sid={(AccountSid or '').strip() or '-'}"
            + (f" error={stream_error}" if stream_error else "")
        ),
        level=level,
    )
    return ResponseBase(success=True, data={"ok": True})


@router.post("/voice/status", response_model=ResponseBase[dict])
async def voice_status_callback(
    request: Request,
    CallSid: Optional[str] = Form(None),  # noqa: N803
    CallStatus: Optional[str] = Form(None),  # noqa: N803
    ErrorCode: Optional[str] = Form(None),  # noqa: N803
    ErrorMessage: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    Duration: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    normalized_status = (CallStatus or "").strip().lower()
    if normalized_status in {"completed", "canceled", "failed", "busy", "no-answer"}:
        await twilio_voice_agent_service.clear_session((CallSid or "").strip())
        if (CallSid or "").strip():
            try:
                async with AsyncSessionLocal() as db:
                    call_repo = CallRepository(db)
                    existing_call = await call_repo.get_by_sip_call_id((CallSid or "").strip())
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
                    CallSid,
                    exc,
                )
    if (CallSid or "").strip():
        if (ErrorCode or "").strip() or (ErrorMessage or "").strip():
            await _append_call_trace(
                CallSid,
                event_type="call_status_error",
                text=(
                    f"code={(ErrorCode or '').strip() or '-'} "
                    f"message={(ErrorMessage or '').strip() or '-'}"
                ),
                level="error",
            )
    logger.info(
        "Twilio status callback. CallSid=%s status=%s From=%s To=%s Duration=%s ErrorCode=%s ErrorMessage=%s",
        CallSid,
        CallStatus,
        From,
        To,
        Duration,
        ErrorCode,
        ErrorMessage,
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": CallSid,
            "status": CallStatus,
            "error_code": ErrorCode,
            "error_message": ErrorMessage,
            "from": From,
            "to": To,
            "duration": Duration,
        },
    )
