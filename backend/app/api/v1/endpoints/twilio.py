import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.api.deps import require_api_key
from app.core.config import settings
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.twilio_webcall_service import TwilioWebCallService
from app.utils.twilio_security import verify_twilio_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)


async def _verify_webhook_or_raise(request: Request) -> None:
    if not settings.twilio_validate_webhooks:
        return

    # Keep local DX intact when Twilio auth token is not configured.
    auth_token = (settings.twilio_auth_token or "").strip()
    if settings.environment == "local" and not auth_token:
        return
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio webhook verification is not configured.",
        )

    form = await request.form()
    form_payload: dict[str, object] = {}
    for key in form.keys():
        values = form.getlist(key)
        if not values:
            form_payload[key] = ""
            continue
        form_payload[key] = values if len(values) > 1 else values[0]

    is_valid, reason = verify_twilio_webhook_request(
        request=request,
        auth_token=auth_token,
        form_data=form_payload,
        tolerance_seconds=settings.twilio_webhook_tolerance_seconds,
    )
    if is_valid:
        return

    logger.warning("Twilio webhook verification failed: %s", reason)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid webhook signature.",
    )


@router.get("/token", response_model=ResponseBase[TwilioTokenResponse])
async def create_voice_sdk_token(
    _auth: None = Depends(require_api_key),
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
    request: Request,
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
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
    request: Request,
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    xml = service.build_incoming_to_client_twiml(identity)
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/status", response_model=ResponseBase[dict])
async def voice_status_callback(
    request: Request,
    CallSid: Optional[str] = Form(None),  # noqa: N803
    CallStatus: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    Duration: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
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
