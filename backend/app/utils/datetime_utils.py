"""Date/time helpers for Tokyo timezone handling."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TOKYO_TZ = ZoneInfo("Asia/Tokyo")


def now_tokyo_aware() -> datetime:
    """Return current time as timezone-aware datetime in Asia/Tokyo."""
    return datetime.now(TOKYO_TZ)


def now_tokyo_naive() -> datetime:
    """
    Return current time in Asia/Tokyo, stored as naive datetime.

    NOTE: DB columns are currently TIMESTAMP WITHOUT TIME ZONE.
    """
    return now_tokyo_aware().replace(tzinfo=None)


def to_tokyo_naive(value: datetime | None) -> datetime | None:
    """Convert datetime to Tokyo local naive for DB comparisons/storage."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(TOKYO_TZ).replace(tzinfo=None)


def to_tokyo_aware(value: datetime | None) -> datetime | None:
    """Convert datetime to timezone-aware Tokyo datetime for API responses."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=TOKYO_TZ)
    return value.astimezone(TOKYO_TZ)
