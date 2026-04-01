"""
Common dependencies for FastAPI endpoints.
"""
import secrets
from typing import AsyncGenerator, Generator

from fastapi import Header, HTTPException, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AsyncSessionLocal, SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for API handlers."""
    async with AsyncSessionLocal() as db:
        yield db


def get_sync_db() -> Generator[Session, None, None]:
    """Sync database session dependency for legacy scripts/endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _extract_api_key(
    *,
    authorization: str | None,
    x_api_key: str | None,
    query_api_key: str | None = None,
) -> str | None:
    bearer = _extract_bearer_token(authorization)
    if bearer:
        return bearer
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if query_api_key and query_api_key.strip():
        return query_api_key.strip()
    return None


def _ensure_api_key_or_raise(
    *,
    authorization: str | None,
    x_api_key: str | None,
    query_api_key: str | None = None,
) -> None:
    if not settings.api_key_auth_required:
        return

    expected_api_key = settings.app_api_key.strip()
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server authentication is not configured.",
        )

    provided_api_key = _extract_api_key(
        authorization=authorization,
        x_api_key=x_api_key,
        query_api_key=query_api_key,
    )
    if not provided_api_key or not secrets.compare_digest(provided_api_key, expected_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized request.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    _ensure_api_key_or_raise(
        authorization=authorization,
        x_api_key=x_api_key,
    )


def verify_websocket_api_key(websocket: WebSocket) -> tuple[bool, str | None]:
    if not settings.api_key_auth_required:
        return True, None

    expected_api_key = settings.app_api_key.strip()
    if not expected_api_key:
        return False, "Server authentication is not configured."

    provided_api_key = _extract_api_key(
        authorization=websocket.headers.get("authorization"),
        x_api_key=websocket.headers.get("x-api-key"),
        query_api_key=websocket.query_params.get("api_key"),
    )
    if not provided_api_key or not secrets.compare_digest(provided_api_key, expected_api_key):
        return False, "Unauthorized websocket request."
    return True, None
