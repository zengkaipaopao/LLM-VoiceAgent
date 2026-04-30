import logging
from dataclasses import dataclass

from app.core.config import settings
from app.schemas.twilio import TwilioTokenResponse
from app.services.twilio.active_inbound_profile import _set_active_inbound_profile_for_number
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

logger = logging.getLogger(__name__)


class TwilioPrepareIncomingOverrideError(ValueError):
    pass


@dataclass(frozen=True)
class TwilioPrepareIncomingOverridePayload:
    to_number: str
    prompt_code: str | None = None
    voice_route: str | None = None
    voice_engine: str | None = None
    voice_name: str | None = None


class TwilioManagementService:
    def __init__(self, *, webcall_service: TwilioWebCallService | None = None) -> None:
        self.webcall_service = webcall_service or TwilioWebCallService()

    def create_voice_sdk_token(self, *, identity: str, ttl_seconds: int) -> TwilioTokenResponse:
        token, normalized_identity, expires_in = self.webcall_service.create_voice_access_token(
            identity,
            ttl_seconds,
        )
        return TwilioTokenResponse(
            token=token,
            identity=normalized_identity,
            expires_in=expires_in,
            twiml_app_sid=settings.twilio_twiml_app_sid,
        )

    async def list_gemini_prebuilt_voices(self, *, force_refresh: bool = False) -> dict:
        voices, source, fetched_at = await _load_official_gemini_voices(
            force_refresh=force_refresh
        )
        return {
            "provider": "gemini",
            "source": source,
            "fetched_at": int(fetched_at),
            "voices": voices,
            "default_voice": "Aoede",
        }

    async def prepare_incoming_voice_override(
        self,
        payload: TwilioPrepareIncomingOverridePayload,
    ) -> dict:
        normalized_number = _normalize_e164_number(payload.to_number)
        if not normalized_number:
            raise TwilioPrepareIncomingOverrideError(
                "to_number must be a valid E.164 phone number."
            )

        queued = await _set_pending_inbound_override_for_number(
            number=normalized_number,
            prompt_code=payload.prompt_code,
            voice_route=payload.voice_route,
            voice_engine=payload.voice_engine,
            voice_name=payload.voice_name,
        )
        active_profile = await _set_active_inbound_profile_for_number(
            number=normalized_number,
            prompt_code=payload.prompt_code,
            voice_route=payload.voice_route,
            voice_engine=payload.voice_engine,
            voice_name=payload.voice_name,
        )
        if not queued:
            raise TwilioPrepareIncomingOverrideError(
                "At least one of prompt_code, voice_route, voice_engine, or voice_name is required."
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
        return {
            "to_number": normalized_number,
            "prompt_code": prompt_token,
            "voice_route": resolved_route,
            "voice_engine": resolved_engine,
            "voice_name": normalized_voice,
            "expires_in_seconds": int(_PENDING_PROMPT_TTL_SECONDS),
            "shared_with_direct_inbound": bool(active_profile),
        }
