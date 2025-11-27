from __future__ import annotations

from app.schemas.models import ModelInfo


class ModelRepository:
    def __init__(self) -> None:
        # In-memory placeholder list; replace with DB/Provider discovery when available.
        self._items = [
            ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai", description="通用对话模型"),
            ModelInfo(id="claude-3-opus", name="Claude 3 Opus", provider="anthropic", description="长上下文对话"),
            ModelInfo(id="gemini-1.5-pro", name="Gemini 1.5 Pro", provider="google", description="多模态支持"),
        ]

    def list(self) -> list[ModelInfo]:
        return self._items


model_repository = ModelRepository()
