from app.repositories.prompts import prompt_repository
from app.schemas.prompts import PromptTemplate


class PromptService:
    def list_prompts(self) -> list[PromptTemplate]:
        return prompt_repository.list()

    def update_prompt(self, prompt_id: str, *, system_prompt: str) -> PromptTemplate:
        return prompt_repository.update(prompt_id, system_prompt)


prompt_service = PromptService()
