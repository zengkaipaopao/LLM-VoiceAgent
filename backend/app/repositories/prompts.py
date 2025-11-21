from __future__ import annotations

from datetime import datetime

from app.schemas.prompts import PromptTemplate


class PromptRepository:
    def __init__(self) -> None:
        self._items = {
            "prompt_1": PromptTemplate(
                id="prompt_1",
                name="售前顾问",
                system_prompt="你是专业的售前助手。",
                updated_at=datetime.now(),
                version="v1.0.0",
            )
        }

    def list(self) -> list[PromptTemplate]:
        return list(self._items.values())

    def update(self, prompt_id: str, system_prompt: str) -> PromptTemplate:
        prompt = self._items[prompt_id]
        prompt.system_prompt = system_prompt
        prompt.updated_at = datetime.now()
        return prompt


prompt_repository = PromptRepository()
