"""Pluggable administrative session storage."""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings


def hash_session_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionRecord:
    user_id: UUID
    csrf_token_hash: str
    ip_address: str | None
    user_agent: str | None


class SessionStore(Protocol):
    async def create(
        self,
        *,
        session_token: str,
        record: SessionRecord,
        ttl_seconds: int,
    ) -> None: ...

    async def get(self, session_token: str) -> SessionRecord | None: ...

    async def revoke(self, session_token: str) -> None: ...


class RedisSessionStore:
    def __init__(self, redis: Redis, *, prefix: str = "llm_voice_agent:admin_session"):
        self.redis = redis
        self.prefix = prefix

    def _key(self, session_token: str) -> str:
        return f"{self.prefix}:{hash_session_secret(session_token)}"

    async def create(
        self,
        *,
        session_token: str,
        record: SessionRecord,
        ttl_seconds: int,
    ) -> None:
        payload = asdict(record)
        payload["user_id"] = str(record.user_id)
        await self.redis.set(
            self._key(session_token),
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            ex=max(1, ttl_seconds),
        )

    async def get(self, session_token: str) -> SessionRecord | None:
        raw = await self.redis.get(self._key(session_token))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return SessionRecord(
                user_id=UUID(str(payload["user_id"])),
                csrf_token_hash=str(payload["csrf_token_hash"]),
                ip_address=str(payload["ip_address"]) if payload.get("ip_address") else None,
                user_agent=str(payload["user_agent"]) if payload.get("user_agent") else None,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self.redis.delete(self._key(session_token))
            return None

    async def revoke(self, session_token: str) -> None:
        await self.redis.delete(self._key(session_token))


_redis_client = Redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)
_session_store: SessionStore = RedisSessionStore(
    _redis_client,
    prefix=settings.auth_session_redis_prefix,
)


def get_session_store() -> SessionStore:
    return _session_store
