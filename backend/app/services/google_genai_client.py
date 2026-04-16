"""
Google GenAI client factory with Vertex AI and Developer API support.
"""
from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types

from app.core.config import settings


def use_vertex_for_google_genai() -> bool:
    return settings.google_vertex_enabled


def google_genai_has_api_key() -> bool:
    return bool((settings.google_api_key or "").strip())


def prepare_google_genai_environment() -> None:
    credential_path = (settings.google_application_credentials or "").strip()
    if not credential_path:
        return

    resolved_path = str(Path(credential_path).expanduser())
    current = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if current != resolved_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = resolved_path


def google_genai_available() -> tuple[bool, str | None]:
    if use_vertex_for_google_genai():
        return True, None
    if google_genai_has_api_key():
        return True, None
    if settings.google_genai_use_vertexai:
        return False, "Vertex AI is enabled but GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION is incomplete."
    return False, "GOOGLE_API_KEY is not configured."


def google_genai_backend_candidates() -> list[str]:
    candidates: list[str] = []
    if use_vertex_for_google_genai():
        candidates.append("vertexai")
    if (
        settings.google_genai_allow_api_key_fallback
        and google_genai_has_api_key()
        and "developer_api" not in candidates
    ):
        candidates.append("developer_api")
    if not candidates and google_genai_has_api_key():
        candidates.append("developer_api")
    return candidates


def is_google_auth_or_permission_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        token in text
        for token in (
            "application default credentials",
            "default credentials were not found",
            "permission 'aiplatform.endpoints.predict' denied",
            "permission denied",
            "403",
            "unauthenticated",
            "authentication",
            "credentials",
            "adc",
        )
    )


def create_google_genai_client(*, api_version: str | None = None, backend: str | None = None) -> genai.Client:
    http_options = types.HttpOptions(api_version=api_version) if api_version else None
    backend_mode = (backend or "").strip().lower()

    if not backend_mode:
        candidates = google_genai_backend_candidates()
        backend_mode = candidates[0] if candidates else ""

    if backend_mode == "vertexai":
        prepare_google_genai_environment()
        kwargs: dict[str, object] = {
            "vertexai": True,
            "project": settings.google_cloud_project,
            "location": settings.google_cloud_location,
        }
        if http_options is not None:
            kwargs["http_options"] = http_options
        return genai.Client(**kwargs)

    api_key = (settings.google_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Google GenAI backend is not configured.")

    kwargs: dict[str, object] = {"api_key": api_key}
    if http_options is not None:
        kwargs["http_options"] = http_options
    return genai.Client(**kwargs)
