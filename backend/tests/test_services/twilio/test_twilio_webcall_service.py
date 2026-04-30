from twilio.jwt.access_token import AccessToken

from app.core.config import settings
from app.services.twilio_webcall_service import TwilioWebCallService


def _set_twilio_config():
    settings.twilio_account_sid = "AC1234567890abcdef1234567890abcd"
    settings.twilio_api_key_sid = "SK1234567890abcdef1234567890abcd"
    settings.twilio_api_key_secret = "secret-value-for-test-only"
    settings.twilio_twiml_app_sid = "AP1234567890abcdef1234567890abcd"
    settings.twilio_phone_number = "+13185551234"


def test_create_voice_access_token_returns_jwt():
    _set_twilio_config()
    service = TwilioWebCallService()

    token, identity, expires_in = service.create_voice_access_token("webcall-tester", ttl_seconds=1800)

    assert token.count(".") == 2
    assert identity == "webcall-tester"
    assert expires_in == 1800

    parsed = AccessToken.from_jwt(token)
    payload = parsed.payload
    assert payload["iss"] == settings.twilio_api_key_sid
    assert payload["sub"] == settings.twilio_account_sid
    assert payload["grants"]["identity"] == "webcall-tester"
    assert payload["grants"]["voice"]["incoming"]["allow"] is True
    assert payload["grants"]["voice"]["outgoing"]["application_sid"] == settings.twilio_twiml_app_sid


def test_build_outbound_twiml_for_number():
    _set_twilio_config()
    service = TwilioWebCallService()

    twiml = service.build_outbound_twiml("+819012345678")

    assert "<Dial" in twiml
    assert "<Number>+819012345678</Number>" in twiml
    assert 'callerId="+13185551234"' in twiml


def test_build_outbound_twiml_returns_error_when_caller_id_missing():
    _set_twilio_config()
    settings.twilio_phone_number = ""
    service = TwilioWebCallService()

    twiml = service.build_outbound_twiml("+819012345678")

    assert "<Say" in twiml
    assert "<Hangup/>" in twiml
