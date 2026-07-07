"""Pluggable authentication providers for administrative users."""

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Protocol

from app.models.auth import AdminUser

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


class AuthenticationProvider(Protocol):
    name: str

    def authenticate(self, user: AdminUser, credential: str) -> bool: ...


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n, r, p, salt_value, digest_value = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value)
        expected = base64.urlsafe_b64decode(digest_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class LocalPasswordAuthProvider:
    name: str = "local"

    def authenticate(self, user: AdminUser, credential: str) -> bool:
        return verify_password(credential, user.password_hash)


class AuthProviderRegistry:
    """Provider boundary for future OIDC/SAML adapters."""

    def __init__(self) -> None:
        self._providers: dict[str, AuthenticationProvider] = {
            "local": LocalPasswordAuthProvider(),
        }

    def get(self, name: str) -> AuthenticationProvider | None:
        return self._providers.get(name)


auth_provider_registry = AuthProviderRegistry()
