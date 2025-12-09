from app.repositories.prompts import PromptRepository, prompt_repository
from app.schemas.prompts import PromptCreate, PromptTemplate, PromptUpdate
from app.services.prompt_builder import build_prompt_instructions


class PromptService:
    def __init__(self, repository: PromptRepository | None = None) -> None:
        self._repository = repository or prompt_repository

    def list_prompts(self) -> list[PromptTemplate]:
        return [self._attach_instructions(prompt) for prompt in self._repository.list()]

    def create_prompt(self, payload: PromptCreate) -> PromptTemplate:
        created = self._repository.create(payload)
        return self._attach_instructions(created)

    def update_prompt(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        updated = self._repository.update(prompt_id, payload)
        return self._attach_instructions(updated)

    def delete_prompt(self, prompt_id: str) -> None:
        self._repository.delete(prompt_id)

    @staticmethod
    def _attach_instructions(prompt: PromptTemplate) -> PromptTemplate:
        instructions = build_prompt_instructions(prompt)
        return prompt.model_copy(update={"instructions": instructions})


prompt_service = PromptService()
