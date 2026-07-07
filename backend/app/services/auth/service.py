"""Administrative login and session lifecycle."""

import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.auth import AdminUser
from app.services.auth.providers import auth_provider_registry
from app.services.auth.session_store import (
    SessionRecord,
    SessionStore,
    get_session_store,
    hash_session_secret,
)
from app.utils.datetime_utils import now_tokyo_naive

_DUMMY_PASSWORD_HASH = (
    "scrypt$32768$8$1$MDAwMDAwMDAwMDAwMDAwMA=="
    "$8bLQYCz4ZK4Cj9yGxFRBLr2DNZyWfQJOfh8NAzC3NXA="
)


@dataclass(frozen=True)
class CreatedSession:
    user: AdminUser
    session_token: str
    csrf_token: str
    expires_at: object


class AuthService:
    def __init__(self, db: AsyncSession, *, session_store: SessionStore | None = None):
        self.db = db
        self.session_store = session_store or get_session_store()

    async def authenticate_local(
        self,
        *,
        username: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> CreatedSession | None:
        normalized = username.strip().lower()
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.username == normalized)
        )
        user = result.scalar_one_or_none()
        now = now_tokyo_naive()

        if user is None:
            # Keep unknown-user and wrong-password work factors comparable.
            from app.services.auth.providers import verify_password

            verify_password(password, _DUMMY_PASSWORD_HASH)
            return None

        if not user.is_active:
            return None
        if user.locked_until and user.locked_until > now:
            return None

        provider = auth_provider_registry.get(user.auth_provider)
        valid = bool(provider and provider.authenticate(user, password))
        if not valid:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.auth_max_failed_attempts:
                user.locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
                user.failed_login_attempts = 0
            await self.db.commit()
            return None

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now

        session_token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(hours=settings.auth_session_hours)
        await self.db.commit()
        await self.db.refresh(user)

        await self.session_store.create(
            session_token=session_token,
            ttl_seconds=settings.auth_session_hours * 3600,
            record=SessionRecord(
                user_id=user.id,
                csrf_token_hash=hash_session_secret(csrf_token),
                ip_address=(ip_address or "")[:64] or None,
                user_agent=(user_agent or "")[:512] or None,
            ),
        )
        return CreatedSession(user, session_token, csrf_token, expires_at)

    async def resolve_session(
        self,
        session_token: str | None,
    ) -> tuple[AdminUser, SessionRecord] | None:
        if not session_token:
            return None
        session = await self.session_store.get(session_token)
        if session is None:
            return None
        result = await self.db.execute(
            select(AdminUser).where(
                AdminUser.id == session.user_id,
                AdminUser.is_active.is_(True),
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            await self.session_store.revoke(session_token)
            return None
        return user, session

    @staticmethod
    def verify_csrf(session: SessionRecord, csrf_token: str | None) -> bool:
        return bool(
            csrf_token
            and secrets.compare_digest(
                session.csrf_token_hash,
                hash_session_secret(csrf_token),
            )
        )

    async def revoke(self, session_token: str | None) -> None:
        if not session_token:
            return
        await self.session_store.revoke(session_token)
