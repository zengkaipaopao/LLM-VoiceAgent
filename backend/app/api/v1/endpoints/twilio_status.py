from typing import Optional

from fastapi import APIRouter, Form, Request

from app.schemas.base import ResponseBase
from app.services.twilio.status_service import (
    TwilioStatusService,
    TwilioStreamStatusPayload,
    TwilioVoiceStatusPayload,
)
from app.services.twilio.webhook_verification import _verify_webhook_or_raise

router = APIRouter()
status_service = TwilioStatusService()


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
    data = await status_service.handle_stream_status(
        TwilioStreamStatusPayload(
            account_sid=AccountSid,
            call_sid=CallSid,
            stream_sid=StreamSid,
            stream_name=StreamName,
            stream_event=StreamEvent,
            stream_error=StreamError,
            timestamp=Timestamp,
        )
    )
    return ResponseBase(success=True, data=data)


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
    data = await status_service.handle_voice_status(
        TwilioVoiceStatusPayload(
            call_sid=CallSid,
            call_status=CallStatus,
            error_code=ErrorCode,
            error_message=ErrorMessage,
            to_number=To,
            from_number=From,
            duration=Duration,
        )
    )
    return ResponseBase(
        success=True,
        data=data,
    )
