from app.repositories.prompts import prompt_repository
from app.schemas.prompts import PromptTemplate, PromptUpdate


class PromptService:
    def list_prompts(self) -> list[PromptTemplate]:
        return prompt_repository.list()

    def update_prompt(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        return prompt_repository.update(prompt_id, payload)


prompt_service = PromptService()
