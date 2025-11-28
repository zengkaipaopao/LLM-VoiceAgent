from __future__ import annotations

import logging
from typing import Callable

from app.core.config import settings
from app.repositories.models import model_repository
from app.schemas.models import ModelInfo
from google import generativeai as genai  # type: ignore
from openai import OpenAI

logger = logging.getLogger(__name__)


def _split_models(config_value: str | None) -> list[str]:
    if not config_value:
        return []
    return [m.strip() for m in config_value.split(",") if m.strip()]


class ModelRegistry:
    """Aggregate models from static config and live provider discovery."""

    def __init__(self) -> None:
        self._cache: dict[str, list[ModelInfo]] = {}
        self._openai_client: OpenAI | None = (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    def _cached(self, key: str, fetcher: Callable[[], list[ModelInfo]]) -> list[ModelInfo]:
        if key in self._cache:
            return self._cache[key]
        models = fetcher()
        self._cache[key] = models
        return models

    def list_models(self) -> list[ModelInfo]:
        static_models = model_repository.list()
        provider_models: list[ModelInfo] = []
        provider_models.extend(self._cached("openai", self._fetch_openai_models))
        provider_models.extend(self._cached("gemini", self._fetch_gemini_models))
        provider_models.extend(self._cached("claude", self._fetch_claude_models))

        dedup: dict[str, ModelInfo] = {}
        for m in (*static_models, *provider_models):
            dedup[m.id] = m
        return list(dedup.values())

    def _fetch_openai_models(self) -> list[ModelInfo]:
        if not self._openai_client:
            return []
        allowlist = set(_split_models(settings.openai_models))
        if not allowlist:
            return []
        try:
            resp = self._openai_client.models.list()
            ids = [m.id for m in resp.data if not allowlist or m.id in allowlist]
            return [ModelInfo(id=i, name=i, provider="openai") for i in ids]
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI 列表模型失败: %s", exc)
            # 回退到配置
            if allowlist:
                return [ModelInfo(id=i, name=i, provider="openai") for i in allowlist]
            return []

    def _fetch_gemini_models(self) -> list[ModelInfo]:
        if not settings.gemini_api_key:
            return []
        allowlist = _split_models(settings.gemini_models or settings.gemini_model)
        if not allowlist:
            return []
        try:
            models = genai.list_models()
            ids = [
                m.name.split("/")[-1]
                for m in models
                if "generateContent" in getattr(m, "supported_generation_methods", [])
                and (not allowlist or m.name.split("/")[-1] in allowlist)
            ]
            return [ModelInfo(id=i, name=i, provider="google") for i in ids]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini 列表模型失败: %s", exc)
            if allowlist:
                return [ModelInfo(id=i, name=i, provider="google") for i in allowlist]
            return []

    def _fetch_claude_models(self) -> list[ModelInfo]:
        # Anthropic 当前无列表接口，使用配置的模型 ID
        if not settings.claude_api_key:
            return []
        configured = _split_models(settings.claude_models)
        return [ModelInfo(id=i, name=i, provider="anthropic") for i in configured]


model_registry = ModelRegistry()
