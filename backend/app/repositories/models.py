from __future__ import annotations

from typing import Iterable

from app.schemas.models import ModelInfo


class ModelRepositoryError(RuntimeError):
    """Raised when model discovery fails."""


class ModelRepository:
    def __init__(self) -> None:
        self._items: list[ModelInfo] = []

    def list(self) -> list[ModelInfo]:
        if not self._items:
            raise ModelRepositoryError("模型列表为空，请检查 Provider 配置或网络连通性。")
        return self._items

    def set_items(self, items: Iterable[ModelInfo]) -> None:
        self._items = list(items)


model_repository = ModelRepository()
