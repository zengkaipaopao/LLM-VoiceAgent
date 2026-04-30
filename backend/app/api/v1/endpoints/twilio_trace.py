from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.exceptions import BusinessException
from app.schemas.base import ResponseBase
from app.services.twilio.debug_audio_runtime import (
    _PCM16K_RESAMPLED_DEBUG_VARIANT,
)
from app.services.twilio.trace_service import (
    TwilioTraceConflictError,
    TwilioTraceService,
)

router = APIRouter()


class TwilioManualAudioInjectRequest(BaseModel):
    call_sid: str = Field(min_length=1)
    audio_base64: str = Field(
        min_length=1,
        description="PCM16 mono audio (16kHz) base64 payload.",
    )
    mime_type: str = Field(default="audio/pcm;rate=16000")


class TwilioAudioLabPrepareRequest(BaseModel):
    audio_base64: str = Field(
        min_length=1,
        description="PCM16 mono audio payload encoded as base64.",
    )
    sample_rate: int = Field(default=16000, ge=4000, le=48000)


class TwilioAudioLabEvaluateRequest(BaseModel):
    audio_base64: str = Field(
        min_length=1,
        description="PCM16 mono audio payload encoded as base64.",
    )
    sample_rate: int = Field(default=16000, ge=4000, le=48000)
    prompt_code: str | None = Field(default=None, min_length=1)
    voice_name: str | None = Field(default=None, min_length=1)
    opening_already_played: bool = Field(default=True)
    variant_id: str | None = Field(default=None, min_length=1)


@router.get("/voice/trace", response_model=ResponseBase[dict])
async def get_voice_trace(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
    since: int = Query(0, ge=0, description="Return events with seq > since"),
):
    return ResponseBase(
        success=True,
        data=await TwilioTraceService().get_trace(call_sid=call_sid, since=since),
    )


@router.get("/voice/trace/latest", response_model=ResponseBase[dict])
async def get_latest_voice_trace_call_sid(
    _auth: None = Depends(require_api_key),
):
    return ResponseBase(
        success=True,
        data=await TwilioTraceService().get_latest_call_sid(),
    )


@router.get("/voice/trace/diagnostics", response_model=ResponseBase[dict])
async def get_voice_trace_diagnostics(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
):
    return ResponseBase(
        success=True,
        data=await TwilioTraceService().get_diagnostics(call_sid=call_sid),
    )


@router.post("/voice/trace/audio-lab/prepare", response_model=ResponseBase[dict])
async def prepare_voice_trace_audio_lab(
    payload: TwilioAudioLabPrepareRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        data = TwilioTraceService().prepare_audio_lab(
            audio_base64=payload.audio_base64,
            sample_rate=payload.sample_rate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ResponseBase(
        success=True,
        data=data,
    )


@router.post("/voice/trace/audio-lab/evaluate", response_model=ResponseBase[dict])
async def evaluate_voice_trace_audio_lab(
    payload: TwilioAudioLabEvaluateRequest,
    _auth: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await TwilioTraceService().evaluate_audio_lab(
            db=db,
            audio_base64=payload.audio_base64,
            sample_rate=payload.sample_rate,
            prompt_code=payload.prompt_code,
            voice_name=payload.voice_name,
            opening_already_played=payload.opening_already_played,
            variant_id=payload.variant_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except BusinessException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini Live evaluation failed: {exc}",
        ) from exc

    return ResponseBase(
        success=True,
        data=data,
    )


@router.get("/voice/trace/inbound-audio", name="twilio_voice_trace_inbound_audio")
async def get_voice_trace_inbound_audio(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
    variant: str = Query(
        _PCM16K_RESAMPLED_DEBUG_VARIANT,
        description=(
            "Debug audio variant: pcm8k_raw, pcm16k_resampled, "
            "followup_pcm8k_raw, or followup_pcm16k_resampled"
        ),
    ),
):
    try:
        wav_path = TwilioTraceService().resolve_inbound_audio_path(
            call_sid=call_sid,
            variant=variant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not wav_path.exists() or not wav_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbound debug audio not found.",
        )
    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=wav_path.name,
    )


@router.post("/voice/trace/inject-audio", response_model=ResponseBase[dict])
async def inject_voice_trace_audio(
    payload: TwilioManualAudioInjectRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        data = await TwilioTraceService().inject_audio(
            call_sid=payload.call_sid,
            audio_base64=payload.audio_base64,
            mime_type=payload.mime_type,
        )
    except TwilioTraceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ResponseBase(
        success=True,
        data=data,
    )


@router.get("/voice/trace/active", response_model=ResponseBase[dict])
async def get_active_voice_trace_calls(
    _auth: None = Depends(require_api_key),
):
    return ResponseBase(
        success=True,
        data=await TwilioTraceService().get_active_calls(),
    )
