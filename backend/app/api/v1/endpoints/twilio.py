from fastapi import APIRouter

from app.core.config import settings
from app.core.model_defaults import require_live_model, resolve_vertex_live_model
from app.services.twilio.debug_audio_runtime import _build_twilio_inbound_debug_capture
from app.services.twilio.live_config import (
    _build_gemini_live_config,
    _resolve_media_stream_bridge_profile,
    _use_manual_vad_control,
    _validate_twilio_activity_mode,
    _validate_twilio_media_stream_bridge_profile,
)
from app.services.twilio.normalizers import _resolve_twilio_inbound_voice_route
from app.services.twilio.pending_overrides import (
    _consume_pending_inbound_override_for_number,
    _set_pending_inbound_override_for_number,
)
from app.services.twilio.prompt_runtime_helpers import (
    _extract_opening_sentence,
    _is_auto_closing_reply,
    _require_opening_sentence,
)
from app.services.twilio.twiml_builders import (
    _build_twilio_media_stream_twiml,
    _candidate_websocket_signature_urls,
    _extract_stream_custom_parameters,
)
from app.services.twilio.voice_catalog import (
    _extract_twilio_google_voice_names,
    _extract_twilio_tts_voice_ids,
)

router = APIRouter()
__all__ = (
    "_build_gemini_live_config",
    "_resolve_media_stream_bridge_profile",
    "_build_twilio_inbound_debug_capture",
    "_build_twilio_media_stream_twiml",
    "_candidate_websocket_signature_urls",
    "_consume_pending_inbound_override_for_number",
    "_extract_opening_sentence",
    "_extract_stream_custom_parameters",
    "_extract_twilio_google_voice_names",
    "_extract_twilio_tts_voice_ids",
    "_is_auto_closing_reply",
    "_require_opening_sentence",
    "_resolve_gemini_live_model",
    "_resolve_twilio_inbound_voice_route",
    "_set_pending_inbound_override_for_number",
    "_use_manual_vad_control",
    "_validate_twilio_activity_mode",
    "_validate_twilio_media_stream_bridge_profile",
)


def _resolve_gemini_live_model(candidate_model: str | None) -> str:
    resolved = require_live_model(
        candidate_model or settings.default_live_model,
        source="Prompt llm_model",
    )
    if settings.google_vertex_enabled:
        return resolve_vertex_live_model(
            resolved,
            fallback_model=settings.default_live_model,
        )
    return resolved
