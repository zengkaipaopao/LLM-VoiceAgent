from fastapi import APIRouter, HTTPException

from app.schemas.prompts import PromptTemplate, PromptUpdate
from app.services.prompt_service import prompt_service

router = APIRouter()


@router.get("", response_model=list[PromptTemplate])
async def list_prompts():
    return prompt_service.list_prompts()


@router.put("/{prompt_id}", response_model=PromptTemplate)
async def update_prompt(prompt_id: str, payload: PromptUpdate):
    prompts = {prompt.id: prompt for prompt in prompt_service.list_prompts()}
    if prompt_id not in prompts:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt_service.update_prompt(prompt_id, system_prompt=payload.system_prompt)
