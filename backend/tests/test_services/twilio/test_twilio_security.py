from urllib.parse import urlsplit

from starlette.requests import Request

from app.utils import twilio_security


def _build_request(url: str, headers: dict[str, str]) -> Request:
    parsed = urlsplit(url)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": parsed.scheme,
        "path": parsed.path,
        "query_string": parsed.query.encode("utf-8"),
        "headers": [
            (key.lower().encode("utf-8"), value.encode("utf-8"))
            for key, value in headers.items()
        ],
        "server": (parsed.hostname or "localhost", parsed.port or 443),
        "client": ("127.0.0.1", 12345),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_verify_twilio_webhook_request_success():
    twilio_security._REPLAY_CACHE.clear()
    url = "https://example.com/api/v1/twilio/voice/status"
    form_data = {"CallSid": "CA123", "CallStatus": "completed"}
    auth_token = "test-token"
    signature = twilio_security.compute_twilio_signature(
        auth_token=auth_token,
        url=url,
        form_data=form_data,
    )
    request = _build_request(
        url,
        {
            "host": "example.com",
            "x-twilio-signature": signature,
            "x-twilio-request-timestamp": "1700000000",
        },
    )

    # keep timestamp check deterministic
    original_time = twilio_security.time.time
    twilio_security.time.time = lambda: 1700000000  # type: ignore[assignment]
    try:
        is_valid, reason = twilio_security.verify_twilio_webhook_request(
            request=request,
            auth_token=auth_token,
            form_data=form_data,
            tolerance_seconds=300,
        )
    finally:
        twilio_security.time.time = original_time  # type: ignore[assignment]

    assert is_valid is True
    assert reason is None


def test_verify_twilio_webhook_request_rejects_replay():
    twilio_security._REPLAY_CACHE.clear()
    url = "https://example.com/api/v1/twilio/voice/status"
    form_data = {"CallSid": "CA123", "CallStatus": "completed"}
    auth_token = "test-token"
    signature = twilio_security.compute_twilio_signature(
        auth_token=auth_token,
        url=url,
        form_data=form_data,
    )
    request = _build_request(
        url,
        {
            "host": "example.com",
            "x-twilio-signature": signature,
            "x-twilio-request-timestamp": "1700000000",
        },
    )

    original_time = twilio_security.time.time
    twilio_security.time.time = lambda: 1700000000  # type: ignore[assignment]
    try:
        first_ok, _ = twilio_security.verify_twilio_webhook_request(
            request=request,
            auth_token=auth_token,
            form_data=form_data,
            tolerance_seconds=300,
        )
        second_ok, second_reason = twilio_security.verify_twilio_webhook_request(
            request=request,
            auth_token=auth_token,
            form_data=form_data,
            tolerance_seconds=300,
        )
    finally:
        twilio_security.time.time = original_time  # type: ignore[assignment]

    assert first_ok is True
    assert second_ok is False
    assert second_reason == "Replay request detected."
