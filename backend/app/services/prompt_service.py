from app.repositories.prompts import PromptRepository, prompt_repository
from app.schemas.prompts import PromptCreate, PromptTemplate, PromptUpdate


class PromptService:
    def __init__(self, repository: PromptRepository | None = None) -> None:
        self._repository = repository or prompt_repository

    def list_prompts(self) -> list[PromptTemplate]:
        return self._repository.list()

    def create_prompt(self, payload: PromptCreate) -> PromptTemplate:
        return self._repository.create(payload)

    def update_prompt(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        return self._repository.update(prompt_id, payload)

    def delete_prompt(self, prompt_id: str) -> None:
        self._repository.delete(prompt_id)


prompt_service = PromptService()
