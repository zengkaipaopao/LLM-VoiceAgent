"""
Twilio WebCall service utilities.

Provides:
- Voice SDK access token generation (JWT, Twilio-compatible claims)
- TwiML XML generation for outbound/inbound voice routing
"""
import html
import re

from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from app.core.config import settings
from app.exceptions import BusinessException


E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.:@-]{1,128}$")
PROMPT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class TwilioWebCallService:
    """Service for Twilio token and TwiML generation."""

    @staticmethod
    def _validate_identity(identity: str) -> str:
        candidate = (identity or "").strip()
        if not candidate:
            return settings.twilio_default_identity
        if not IDENTITY_PATTERN.fullmatch(candidate):
            raise BusinessException(
                "Identity contains invalid characters. Allowed: letters, digits, _ . : @ -"
            )
        return candidate

    @staticmethod
    def _validate_token_config() -> None:
        required = {
            "twilio_account_sid": settings.twilio_account_sid,
            "twilio_api_key_sid": settings.twilio_api_key_sid,
            "twilio_api_key_secret": settings.twilio_api_key_secret,
            "twilio_twiml_app_sid": settings.twilio_twiml_app_sid,
        }
        missing = [key for key, value in required.items() if not str(value or "").strip()]
        if missing:
            raise BusinessException(f"Twilio configuration missing: {', '.join(missing)}")

    @staticmethod
    def _normalize_phone_number_for_e164(number: str) -> str:
        # Accept common human-readable separators in UI input.
        return re.sub(r"[\s\u3000\-()]", "", (number or "").strip())

    @staticmethod
    def _validate_phone_number(number: str) -> str:
        value = TwilioWebCallService._normalize_phone_number_for_e164(number)
        if not E164_PATTERN.fullmatch(value):
            raise BusinessException("Phone number must be E.164 format, e.g. +13185551234")
        return value

    @staticmethod
    def _normalize_prompt_code(prompt_code: str | None) -> str | None:
        value = (prompt_code or "").strip()
        if not value:
            return None
        if not PROMPT_CODE_PATTERN.fullmatch(value):
            return None
        return value

    def create_voice_access_token(self, identity: str, ttl_seconds: int = 3600) -> tuple[str, str, int]:
        """
        Create Twilio-compatible Voice SDK JWT token.

        Returns:
            token, normalized_identity, expires_in_seconds
        """
        self._validate_token_config()
        normalized_identity = self._validate_identity(identity)

        if ttl_seconds < 60 or ttl_seconds > 86_400:
            raise BusinessException("ttl_seconds must be between 60 and 86400")

        voice_grant = VoiceGrant(
            incoming_allow=True,
            outgoing_application_sid=settings.twilio_twiml_app_sid,
        )
        access_token = AccessToken(
            settings.twilio_account_sid,
            settings.twilio_api_key_sid,
            settings.twilio_api_key_secret,
            identity=normalized_identity,
            ttl=int(ttl_seconds),
        )
        access_token.add_grant(voice_grant)
        token = access_token.to_jwt()
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token, normalized_identity, int(ttl_seconds)

    def build_outbound_twiml(self, to: str) -> str:
        """
        Build TwiML for browser-originated outbound call.
        """
        destination = (to or "").strip()
        if not destination:
            return self._say_and_hangup("No destination number was provided.")

        if destination.startswith("client:"):
            target_identity = html.escape(destination.replace("client:", "", 1).strip())
            if not target_identity:
                return self._say_and_hangup("Invalid client identity.")
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Dial answerOnBridge=\"true\"><Client>{target_identity}</Client></Dial></Response>"
            )

        try:
            normalized_to = self._validate_phone_number(destination)
        except BusinessException:
            return self._say_and_hangup("Destination must be in E.164 format, for example +13185551234.")

        caller_id = str(settings.twilio_phone_number or "").strip()
        if not E164_PATTERN.fullmatch(caller_id):
            return self._say_and_hangup(
                "Server is missing valid Twilio caller ID. Configure TWILIO_PHONE_NUMBER in E.164 format."
            )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Dial answerOnBridge=\"true\" callerId=\"{html.escape(caller_id)}\">"
            f"<Number>{html.escape(normalized_to)}</Number></Dial></Response>"
        )

    def resolve_incoming_prompt_code(self, *, prompt_code: str | None, to_number: str | None) -> str | None:
        """
        Resolve prompt for inbound PSTN call.

        Priority:
        1) prompt_code in webhook query params
        2) per-number mapping from TWILIO_INCOMING_PROMPT_MAP
        3) TWILIO_DEFAULT_PROMPT_CODE
        """
        from_query = self._normalize_prompt_code(prompt_code)
        if from_query:
            return from_query

        normalized_to: str | None = None
        try:
            normalized_to = self._validate_phone_number((to_number or "").strip())
        except BusinessException:
            normalized_to = None

        if normalized_to:
            mapped = settings.twilio_incoming_prompt_mapping.get(normalized_to)
            from_map = self._normalize_prompt_code(mapped)
            if from_map:
                return from_map

        return self._normalize_prompt_code(settings.twilio_default_prompt_code)

    def build_incoming_to_client_twiml(self, identity: str, prompt_code: str | None = None) -> str:
        """
        Build TwiML to route PSTN incoming call to a browser client identity.
        """
        normalized_identity = self._validate_identity(identity)
        normalized_prompt = self._normalize_prompt_code(prompt_code)

        if not normalized_prompt:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Dial answerOnBridge=\"true\"><Client>{html.escape(normalized_identity)}</Client></Dial></Response>"
            )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Dial answerOnBridge=\"true\"><Client>"
            f"<Identity>{html.escape(normalized_identity)}</Identity>"
            f"<Parameter name=\"prompt_code\" value=\"{html.escape(normalized_prompt)}\" />"
            "</Client></Dial></Response>"
        )

    @staticmethod
    def _say_and_hangup(message: str) -> str:
        safe = html.escape(message)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say voice=\"alice\">{safe}</Say><Hangup/></Response>"
        )
