from __future__ import annotations

import logging
from typing import Callable

from app.core.config import settings
from app.repositories.models import ModelRepositoryError, model_repository
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
        try:
            static_models = model_repository.list()
        except ModelRepositoryError:
            static_models = []
        provider_models: list[ModelInfo] = []
        if self._openai_client:
            provider_models.extend(self._cached("openai", self._fetch_openai_models))
        if settings.gemini_api_key:
            provider_models.extend(self._cached("gemini", self._fetch_gemini_models))
        if settings.claude_api_key:
            provider_models.extend(self._cached("claude", self._fetch_claude_models))

        dedup: dict[str, ModelInfo] = {}
        for m in (*static_models, *provider_models):
            dedup[m.id] = m
        if not dedup:
            raise RuntimeError("无法列出任何模型，请检查 Provider 配置。")
        model_list = list(dedup.values())
        model_repository.set_items(model_list)
        return model_list

    def _fetch_openai_models(self) -> list[ModelInfo]:
        if not self._openai_client:
            raise RuntimeError("未配置 OpenAI API Key，无法拉取 OpenAI 模型。")
        try:
            resp = self._openai_client.models.list()
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI 列表模型失败")
            raise RuntimeError("调用 OpenAI 模型列表失败，请检查网络或密钥。") from exc
        ids = [m.id for m in resp.data]
        if not ids:
            raise RuntimeError("OpenAI 返回空列表。")
        return [ModelInfo(id=i, name=i, provider="openai") for i in ids]

    def _fetch_gemini_models(self) -> list[ModelInfo]:
        allowlist = _split_models(settings.gemini_models or settings.gemini_model)
        try:
            models = genai.list_models()
            ids = [
                m.name.split("/")[-1]
                for m in models
                if "generateContent" in getattr(m, "supported_generation_methods", [])
                and (not allowlist or m.name.split("/")[-1] in allowlist)
            ]
            if not ids:
                raise RuntimeError("Gemini 返回空列表，请检查 GEMINI_MODELS 配置。")
            return [ModelInfo(id=i, name=i, provider="google") for i in ids]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Gemini 列表模型失败")
            raise RuntimeError("调用 Gemini 模型列表失败，请检查网络或密钥。") from exc

    def _fetch_claude_models(self) -> list[ModelInfo]:
        # Anthropic 当前无列表接口，使用配置的模型 ID
        configured = _split_models(settings.claude_models)
        if not configured:
            raise RuntimeError("未配置 CLAUDE_MODELS，无法列出 Claude 模型。")
        return [ModelInfo(id=i, name=i, provider="anthropic") for i in configured]


model_registry = ModelRegistry()
