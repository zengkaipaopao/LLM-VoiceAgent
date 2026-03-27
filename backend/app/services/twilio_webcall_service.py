"""
Twilio WebCall service utilities.

Provides:
- Voice SDK access token generation (JWT, Twilio-compatible claims)
- TwiML XML generation for outbound/inbound voice routing
"""
import base64
import hashlib
import hmac
import html
import json
import re
import time
from uuid import uuid4

from app.core.config import settings
from app.exceptions import BusinessException


E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9_.:@-]{1,128}$")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


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
    def _validate_phone_number(number: str) -> str:
        value = (number or "").strip()
        if not E164_PATTERN.fullmatch(value):
            raise BusinessException("Phone number must be E.164 format, e.g. +13185551234")
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

        now = int(time.time())
        exp = now + int(ttl_seconds)

        header = {"alg": "HS256", "typ": "JWT", "cty": "twilio-fpa;v=1"}
        grants = {
            "identity": normalized_identity,
            "voice": {
                "incoming": {"allow": True},
                "outgoing": {"application_sid": settings.twilio_twiml_app_sid},
            },
        }
        payload = {
            "jti": f"{settings.twilio_api_key_sid}-{uuid4()}",
            "iss": settings.twilio_api_key_sid,
            "sub": settings.twilio_account_sid,
            "iat": now,
            "nbf": now - 1,
            "exp": exp,
            "grants": grants,
        }

        encoded_header = _b64url_encode(
            json.dumps(header, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        )
        encoded_payload = _b64url_encode(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(
            settings.twilio_api_key_secret.encode("utf-8"),
            signing_input,
            digestmod=hashlib.sha256,
        ).digest()
        encoded_signature = _b64url_encode(signature)

        token = f"{encoded_header}.{encoded_payload}.{encoded_signature}"
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

    def build_incoming_to_client_twiml(self, identity: str) -> str:
        """
        Build TwiML to route PSTN incoming call to a browser client identity.
        """
        normalized_identity = self._validate_identity(identity)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Dial answerOnBridge=\"true\"><Client>{html.escape(normalized_identity)}</Client></Dial></Response>"
        )

    @staticmethod
    def _say_and_hangup(message: str) -> str:
        safe = html.escape(message)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say voice=\"alice\">{safe}</Say><Hangup/></Response>"
        )
