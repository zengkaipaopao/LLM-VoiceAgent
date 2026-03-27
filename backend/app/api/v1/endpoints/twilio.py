import logging
from typing import Optional

from fastapi import APIRouter, Form, Query
from fastapi.responses import Response

from app.core.config import settings
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.twilio_webcall_service import TwilioWebCallService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/token", response_model=ResponseBase[TwilioTokenResponse])
async def create_voice_sdk_token(
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
    ttl_seconds: int = Query(3600, ge=60, le=86_400),
):
    service = TwilioWebCallService()
    token, normalized_identity, expires_in = service.create_voice_access_token(identity, ttl_seconds)
    return ResponseBase(
        success=True,
        data=TwilioTokenResponse(
            token=token,
            identity=normalized_identity,
            expires_in=expires_in,
            twiml_app_sid=settings.twilio_twiml_app_sid,
        ),
    )


@router.post("/voice/twiml")
async def twiml_app_voice_webhook(
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
):
    service = TwilioWebCallService()
    xml = service.build_outbound_twiml(To or "")
    logger.info(
        "Twilio TwiML app webhook called. CallSid=%s From=%s To=%s prompt_code=%s",
        CallSid,
        From,
        To,
        prompt_code,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/incoming")
async def incoming_voice_webhook(
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
):
    service = TwilioWebCallService()
    xml = service.build_incoming_to_client_twiml(identity)
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/status", response_model=ResponseBase[dict])
async def voice_status_callback(
    CallSid: Optional[str] = Form(None),  # noqa: N803
    CallStatus: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    Duration: Optional[str] = Form(None),  # noqa: N803
):
    logger.info(
        "Twilio status callback. CallSid=%s status=%s From=%s To=%s Duration=%s",
        CallSid,
        CallStatus,
        From,
        To,
        Duration,
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": CallSid,
            "status": CallStatus,
            "from": From,
            "to": To,
            "duration": Duration,
        },
    )
