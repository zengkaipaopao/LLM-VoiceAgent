"""
Common dependencies for FastAPI endpoints.
"""
import secrets
from typing import AsyncGenerator, Generator

from fastapi import Depends, Header, HTTPException, Request, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AsyncSessionLocal, SessionLocal
from app.models.auth import AdminUser
from app.services.auth import AuthService


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


def _api_key_is_valid(
    *,
    authorization: str | None,
    x_api_key: str | None,
) -> bool:
    expected = settings.app_api_key.strip()
    provided = _extract_api_key(
        authorization=authorization,
        x_api_key=x_api_key,
    )
    return bool(expected and provided and secrets.compare_digest(provided, expected))


async def _resolve_admin_session(
    request: Request,
    db: AsyncSession,
) -> AdminUser | None:
    resolved = await AuthService(db).resolve_session(
        request.cookies.get(settings.auth_session_cookie_name)
    )
    if resolved is None:
        return None
    user, session = resolved
    csrf_token = request.cookies.get(settings.auth_csrf_cookie_name)
    request.state.admin_user = user
    request.state.admin_session = session
    request.state.csrf_token = csrf_token or ""

    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        header_token = request.headers.get("x-csrf-token")
        if (
            not csrf_token
            or not header_token
            or not secrets.compare_digest(csrf_token, header_token)
            or not AuthService.verify_csrf(session, header_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token.",
            )
    return user


async def require_admin_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    user = await _resolve_admin_session(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


async def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AdminUser | None:
    """Allow a browser admin session or a configured machine API key."""
    user = await _resolve_admin_session(request, db)
    if user is not None:
        return user
    if _api_key_is_valid(authorization=authorization, x_api_key=x_api_key):
        request.state.machine_authenticated = True
        return None
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
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


async def verify_admin_websocket_session(websocket: WebSocket) -> tuple[bool, str | None]:
    """Authenticate browser Live WebSockets without affecting Twilio streams."""
    session_token = websocket.cookies.get(settings.auth_session_cookie_name)
    async with AsyncSessionLocal() as db:
        resolved = await AuthService(db).resolve_session(session_token)
        if resolved is None:
            return False, "Authentication required."
        await db.commit()
    return True, None
