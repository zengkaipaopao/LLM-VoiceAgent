from fastapi import APIRouter

from app.core.config import settings
from app.schemas.base import ResponseBase

router = APIRouter()


@router.get("/health", response_model=ResponseBase[dict])
async def health_check():
    return ResponseBase(success=True, data={"status": "ok"})


@router.get("/health/capabilities", response_model=ResponseBase[dict])
async def capability_matrix():
    return ResponseBase(
        success=True,
        data={
            "chat_prompt_testbed": {"status": "implemented"},
            "gemini_live_gateway": {
                "status": "implemented" if settings.live_gateway_enabled else "disabled",
                "requires": ["GOOGLE_API_KEY"],
            },
            "twilio_webcall": {
                "status": "implemented" if settings.twilio_webcall_enabled else "disabled",
                "requires": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_TWIML_APP_SID"],
            },
            "provider_support": {
                "gemini": "implemented",
                "openai": "planned",
                "claude": "planned",
            },
            "sip_call_control": {
                "status": "planned",
                "note": "Outbound answer/transfer/end requires SIP integration.",
            },
            "calendar_sync": {
                "status": "planned",
                "note": "Appointment create/update/cancel requires calendar integration.",
            },
        },
    )
