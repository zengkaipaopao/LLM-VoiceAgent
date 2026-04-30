from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.twilio.incoming_service import (
    TwilioAgentTurnPayload,
    TwilioIncomingService,
    TwilioIncomingVoicePayload,
    TwilioTwiMLAppPayload,
)
from app.services.twilio.webhook_verification import _verify_webhook_or_raise

router = APIRouter()
incoming_service = TwilioIncomingService()


@router.post("/voice/twiml")
async def twiml_app_voice_webhook(
    request: Request,
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
    voice_route: Optional[str] = Form(None),
    voice_engine: Optional[str] = Form(None),
    voice_name: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
    xml = await incoming_service.build_twiml_app_voice_response(
        TwilioTwiMLAppPayload(
            to_number=To,
            from_number=From,
            call_sid=CallSid,
            prompt_code=prompt_code,
            voice_route=voice_route,
            voice_engine=voice_engine,
            voice_name=voice_name,
        )
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/incoming")
async def incoming_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
    prompt_code: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    voice_route: Optional[str] = Query(
        default=None,
        description=(
            "Inbound AI voice route: gather or official_conversational_agents. "
            "Legacy aliases media_stream_live and official_demo_live are normalized "
            "to official_conversational_agents."
        ),
    ),
    voice_engine: Optional[str] = Query(
        default=None,
        description="Inbound AI voice engine: twilio or gemini.",
    ),
    voice_name: Optional[str] = Query(
        default=None,
        description="Optional Gemini Live voice override.",
    ),
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    xml = await incoming_service.build_incoming_voice_response(
        request=request,
        db=db,
        payload=TwilioIncomingVoicePayload(
            identity=identity,
            prompt_code=prompt_code,
            mode=mode,
            voice_route=voice_route,
            voice_engine=voice_engine,
            voice_name=voice_name,
            to_number=To,
            from_number=From,
            call_sid=CallSid,
        ),
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/agent/turn", name="twilio_voice_agent_turn")
async def twilio_voice_agent_turn(
    request: Request,
    db: AsyncSession = Depends(get_db),
    prompt_code: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    SpeechResult: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    xml = await incoming_service.build_agent_turn_response(
        request=request,
        db=db,
        payload=TwilioAgentTurnPayload(
            prompt_code=prompt_code,
            call_sid=CallSid,
            to_number=To,
            speech_result=SpeechResult,
        ),
    )
    return Response(content=xml, media_type="application/xml")
