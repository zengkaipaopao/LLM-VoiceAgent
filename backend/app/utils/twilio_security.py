"""
Twilio webhook request verification helpers.
"""
import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Mapping
from urllib.parse import urlunsplit

from fastapi import Request


_REPLAY_CACHE: dict[str, int] = {}


def _normalize_header_value(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    return raw_value.split(",", 1)[0].strip() or None


def _build_public_url(request: Request) -> str:
    forwarded_proto = _normalize_header_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _normalize_header_value(request.headers.get("x-forwarded-host"))

    scheme = forwarded_proto or request.url.scheme
    netloc = forwarded_host or request.headers.get("host") or request.url.netloc

    return urlunsplit((scheme, netloc, request.url.path, request.url.query, ""))


def _canonical_params(form_data: Mapping[str, object]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key in sorted(form_data.keys()):
        raw_value = form_data[key]
        if isinstance(raw_value, (list, tuple)):
            values = [str(item) for item in raw_value]
        else:
            values = [str(raw_value)]
        for value in sorted(values):
            pairs.append((key, value))
    return pairs


def compute_twilio_signature(*, auth_token: str, url: str, form_data: Mapping[str, object]) -> str:
    payload = [url]
    for key, value in _canonical_params(form_data):
        payload.append(f"{key}{value}")
    expected = hmac.new(
        auth_token.encode("utf-8"),
        "".join(payload).encode("utf-8"),
        digestmod=hashlib.sha1,
    ).digest()
    return base64.b64encode(expected).decode("ascii")


def _prune_replay_cache(now_ts: int) -> None:
    expired_keys = [key for key, expires_at in _REPLAY_CACHE.items() if expires_at <= now_ts]
    for key in expired_keys:
        _REPLAY_CACHE.pop(key, None)


def _enforce_replay_guard(
    *,
    request: Request,
    signature: str,
    tolerance_seconds: int,
) -> tuple[bool, str | None]:
    now_ts = int(time.time())
    _prune_replay_cache(now_ts)

    timestamp_header = request.headers.get("x-twilio-request-timestamp")
    if timestamp_header:
        try:
            request_ts = int(timestamp_header)
        except ValueError:
            return False, "Invalid Twilio request timestamp header."
        if abs(now_ts - request_ts) > tolerance_seconds:
            return False, "Twilio webhook timestamp is outside the allowed window."
        replay_key = f"{signature}:{request_ts}"
    else:
        # Fallback: deduplicate on signature within tolerance window.
        replay_key = signature

    if replay_key in _REPLAY_CACHE:
        return False, "Replay request detected."

    _REPLAY_CACHE[replay_key] = now_ts + tolerance_seconds
    return True, None


def verify_twilio_webhook_request(
    *,
    request: Request,
    auth_token: str,
    form_data: Mapping[str, object],
    tolerance_seconds: int = 300,
) -> tuple[bool, str | None]:
    signature = request.headers.get("x-twilio-signature")
    if not signature:
        return False, "Missing Twilio signature header."

    expected_signature = compute_twilio_signature(
        auth_token=auth_token,
        url=_build_public_url(request),
        form_data=form_data,
    )
    if not secrets.compare_digest(signature, expected_signature):
        return False, "Twilio signature verification failed."

    return _enforce_replay_guard(
        request=request,
        signature=signature,
        tolerance_seconds=tolerance_seconds,
    )
