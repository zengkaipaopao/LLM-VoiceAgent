from app.repositories.prompts import prompt_repository
from app.schemas.prompts import PromptCreate, PromptTemplate, PromptUpdate


class PromptService:
    def list_prompts(self) -> list[PromptTemplate]:
        return prompt_repository.list()

    def create_prompt(self, payload: PromptCreate) -> PromptTemplate:
        return prompt_repository.create(payload)

    def update_prompt(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        return prompt_repository.update(prompt_id, payload)

    def delete_prompt(self, prompt_id: str) -> None:
        prompt_repository.delete(prompt_id)


prompt_service = PromptService()
