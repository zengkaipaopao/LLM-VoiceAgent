from fastapi import APIRouter, HTTPException

from app.schemas.prompts import PromptCreate, PromptTemplate, PromptUpdate
from app.services.prompt_service import prompt_service

router = APIRouter()


@router.get("", response_model=list[PromptTemplate])
async def list_prompts():
    return prompt_service.list_prompts()


@router.post("", response_model=PromptTemplate, status_code=201)
async def create_prompt(payload: PromptCreate):
    return prompt_service.create_prompt(payload)


@router.put("/{prompt_id}", response_model=PromptTemplate)
async def update_prompt(prompt_id: str, payload: PromptUpdate):
    try:
        return prompt_service.update_prompt(prompt_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Prompt not found") from exc


@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(prompt_id: str):
    try:
        prompt_service.delete_prompt(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Prompt not found") from exc
