from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.services.twilio_voice import twilio_voice_service


router = APIRouter()


@router.post("/voice", response_class=PlainTextResponse)
async def twilio_voice_webhook(request: Request) -> PlainTextResponse:
    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature")
    params = list(form.multi_items())
    twilio_voice_service.validate_signature(str(request.url), params, signature)

    payload = {key: value for key, value in params}
    twiml = await twilio_voice_service.build_twiml(payload)
    return PlainTextResponse(content=twiml, media_type="text/xml")


class TwilioTokenRequest(BaseModel):
    identity: str | None = None


@router.post("/token")
async def issue_twilio_token(payload: TwilioTokenRequest) -> dict:
    identity = payload.identity.strip() if payload.identity else f"web-{uuid4().hex[:8]}"
    token = twilio_voice_service.generate_client_token(identity)
    return {"identity": identity, "token": token}
