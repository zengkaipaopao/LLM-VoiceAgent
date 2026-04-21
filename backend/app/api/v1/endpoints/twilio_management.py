import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_api_key
from app.core.config import settings
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_prompt_code_token,
    _normalize_twilio_voice_route,
    _normalize_voice_engine,
    _normalize_voice_name_token,
)
from app.services.twilio.pending_overrides import (
    _PENDING_PROMPT_TTL_SECONDS,
    _set_pending_inbound_override_for_number,
)
from app.services.twilio.voice_catalog import _load_official_gemini_voices
from app.services.twilio_webcall_service import TwilioWebCallService

router = APIRouter()
logger = logging.getLogger(__name__)


class TwilioPrepareIncomingOverrideRequest(BaseModel):
    to_number: str = Field(min_length=1, description="Target Twilio inbound number in E.164 format.")
    prompt_code: str | None = Field(default=None, min_length=1, max_length=64)
    voice_route: str | None = Field(default=None, min_length=1, max_length=64)
    voice_engine: str | None = Field(default="gemini", min_length=1, max_length=32)
    voice_name: str | None = Field(default=None, min_length=1, max_length=128)


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


@router.get("/voice/voices", response_model=ResponseBase[dict])
async def list_gemini_prebuilt_voices(
    force_refresh: bool = Query(default=False, description="Force refresh from official source."),
):
    voices, source, fetched_at = await _load_official_gemini_voices(force_refresh=force_refresh)
    return ResponseBase(
        success=True,
        data={
            "provider": "gemini",
            "source": source,
            "fetched_at": int(fetched_at),
            "voices": voices,
            "default_voice": "Aoede",
        },
    )


@router.post("/voice/incoming/prepare", response_model=ResponseBase[dict])
async def prepare_incoming_voice_override(
    payload: TwilioPrepareIncomingOverrideRequest,
    _auth: None = Depends(require_api_key),
):
    normalized_number = _normalize_e164_number(payload.to_number)
    if not normalized_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="to_number must be a valid E.164 phone number.",
        )

    queued = await _set_pending_inbound_override_for_number(
        number=normalized_number,
        prompt_code=payload.prompt_code,
        voice_route=payload.voice_route,
        voice_engine=payload.voice_engine,
        voice_name=payload.voice_name,
    )
    if not queued:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of prompt_code, voice_route, voice_engine, or voice_name is required.",
        )

    prompt_token = _normalize_prompt_code_token(payload.prompt_code)
    resolved_route = _normalize_twilio_voice_route(payload.voice_route)
    resolved_engine = _normalize_voice_engine(payload.voice_engine)
    normalized_voice = _normalize_voice_name_token(payload.voice_name)
    logger.info(
        (
            "Prepared pending inbound override. "
            "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s ttl_seconds=%s"
        ),
        normalized_number,
        prompt_token,
        resolved_route,
        resolved_engine,
        normalized_voice,
        int(_PENDING_PROMPT_TTL_SECONDS),
    )
    return ResponseBase(
        success=True,
        data={
            "to_number": normalized_number,
            "prompt_code": prompt_token,
            "voice_route": resolved_route,
            "voice_engine": resolved_engine,
            "voice_name": normalized_voice,
            "expires_in_seconds": int(_PENDING_PROMPT_TTL_SECONDS),
        },
    )
