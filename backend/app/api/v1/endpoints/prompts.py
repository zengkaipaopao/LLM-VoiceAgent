"""
Prompt templates API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.base import ResponseBase
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.services.prompt_service import PromptService

router = APIRouter()


@router.get("", response_model=ResponseBase[PromptTemplateListResponse])
async def list_templates(
    category: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    prompt_service = PromptService(db)
    templates = await prompt_service.list_templates(category=category, active_only=active_only)

    return ResponseBase(
        success=True,
        data=PromptTemplateListResponse(
            templates=[PromptTemplateResponse.from_orm(t) for t in templates],
            total=len(templates),
        ),
    )


@router.get("/{template_id}", response_model=ResponseBase[PromptTemplateResponse])
async def get_template(template_id: UUID, db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)
    template = await prompt_service.get_template_by_id(str(template_id))

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.get("/code/{code}", response_model=ResponseBase[PromptTemplateResponse])
async def get_template_by_code(code: str, db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)
    template = await prompt_service.get_template(code)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{code}' not found",
        )

    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.post("", response_model=ResponseBase[PromptTemplateResponse], status_code=status.HTTP_201_CREATED)
async def create_template(template_in: PromptTemplateCreate, db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)

    if await prompt_service.get_template(template_in.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template code '{template_in.code}' already exists",
        )

    template = await prompt_service.create_template(**template_in.dict())

    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.put("/{template_id}", response_model=ResponseBase[PromptTemplateResponse])
async def update_template(
    template_id: UUID,
    template_in: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    prompt_service = PromptService(db)
    template = await prompt_service.get_template_by_id(str(template_id))

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    update_data = template_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.delete("/{template_id}", response_model=ResponseBase[None], status_code=status.HTTP_200_OK)
async def delete_template(template_id: UUID, db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)
    template = await prompt_service.get_template_by_id(str(template_id))

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    await db.delete(template)
    await db.commit()
    return ResponseBase(success=True, message="Template deleted successfully", data=None)
