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
                "mode": settings.google_genai_backend_mode,
                "requires": ["GOOGLE_API_KEY or Vertex AI ADC"],
            },
            "gemini_generate_gateway": {
                "status": "implemented" if settings.google_genai_backend_enabled else "disabled",
                "mode": settings.google_genai_backend_mode,
                "requires": ["GOOGLE_API_KEY or Vertex AI ADC"],
            },
            "twilio_webcall": {
                "status": "implemented" if settings.twilio_webcall_enabled else "disabled",
                "requires": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_TWIML_APP_SID"],
                "configured_phone_number": (settings.twilio_phone_number or "").strip() or None,
            },
            "twilio_inbound_voice_engine": {
                "status": "implemented",
                "default_engine": settings.twilio_incoming_voice_engine,
                "supported_engines": ["twilio", "gemini"],
                "supported_routes": [
                    "gather",
                    "official_conversational_agents",
                ],
                "gemini_activity_mode": "auto_or_manual",
                "gemini_activity_handling": "start_of_activity_interrupts",
                "runtime_store_backend": settings.twilio_runtime_store_backend,
            },
            "google_conversational_agents_twilio_adapter": {
                "status": "implemented" if settings.twilio_official_ca_configured else "disabled",
                "requires": [
                    "TWILIO_OFFICIAL_CA_DEPLOYMENT_ID or TWILIO_OFFICIAL_CA_AGENT_ID",
                    "Google ADC with roles/ces.client",
                ],
                "environment": settings.twilio_official_ca_environment,
            },
            "provider_support": {
                "gemini": "implemented",
                "openai": "adapter_reserved_not_implemented",
                "claude": "planned",
            },
            "live_provider_routing": {
                "status": "implemented",
                "default_provider": settings.default_live_provider,
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
