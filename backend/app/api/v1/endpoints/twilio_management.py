from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_api_key
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.twilio.management_service import (
    TwilioManagementService,
    TwilioPrepareIncomingOverrideError,
    TwilioPrepareIncomingOverridePayload,
)

router = APIRouter()
management_service = TwilioManagementService()


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
    token_response = management_service.create_voice_sdk_token(
        identity=identity,
        ttl_seconds=ttl_seconds,
    )
    return ResponseBase(
        success=True,
        data=token_response,
    )


@router.get("/voice/voices", response_model=ResponseBase[dict])
async def list_gemini_prebuilt_voices(
    force_refresh: bool = Query(default=False, description="Force refresh from official source."),
):
    data = await management_service.list_gemini_prebuilt_voices(force_refresh=force_refresh)
    return ResponseBase(
        success=True,
        data=data,
    )


@router.post("/voice/incoming/prepare", response_model=ResponseBase[dict])
async def prepare_incoming_voice_override(
    payload: TwilioPrepareIncomingOverrideRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        data = await management_service.prepare_incoming_voice_override(
            TwilioPrepareIncomingOverridePayload(
                to_number=payload.to_number,
                prompt_code=payload.prompt_code,
                voice_route=payload.voice_route,
                voice_engine=payload.voice_engine,
                voice_name=payload.voice_name,
            )
        )
    except TwilioPrepareIncomingOverrideError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ResponseBase(
        success=True,
        data=data,
    )
