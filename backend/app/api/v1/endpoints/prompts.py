"""
Prompt templates API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_db
# Use new schemas
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse
)
from app.schemas.base import ResponseBase
from app.services.prompt_service import PromptService

router = APIRouter()


@router.get("", response_model=ResponseBase[PromptTemplateListResponse])
async def list_templates(
    category: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    List all prompt templates.
    """
    prompt_service = PromptService(db)
    templates = prompt_service.list_templates(category=category, active_only=active_only)
    
    return ResponseBase(
        success=True,
        data=PromptTemplateListResponse(
            templates=[PromptTemplateResponse.from_orm(t) for t in templates],
            total=len(templates)
        )
    )


@router.get("/{template_id}", response_model=ResponseBase[PromptTemplateResponse])
async def get_template(
    template_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a specific template by ID.
    """
    prompt_service = PromptService(db)
    template = prompt_service.get_template_by_id(str(template_id))
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.get("/code/{code}", response_model=ResponseBase[PromptTemplateResponse])
async def get_template_by_code(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific template by code.
    """
    prompt_service = PromptService(db)
    template = prompt_service.get_template(code)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{code}' not found"
        )
    
    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.post("", response_model=ResponseBase[PromptTemplateResponse], status_code=status.HTTP_201_CREATED)
async def create_template(
    template_in: PromptTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new prompt template.
    """
    prompt_service = PromptService(db)
    
    # Check if code exists
    if prompt_service.get_template(template_in.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template code '{template_in.code}' already exists"
        )
    
    # Create template
    template = prompt_service.create_template(
        **template_in.dict()
    )
    
    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.put("/{template_id}", response_model=ResponseBase[PromptTemplateResponse])
async def update_template(
    template_id: UUID,
    template_in: PromptTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a prompt template.
    """
    prompt_service = PromptService(db)
    template = prompt_service.get_template_by_id(str(template_id))
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    update_data = template_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return ResponseBase(success=True, data=PromptTemplateResponse.from_orm(template))


@router.delete("/{template_id}", response_model=ResponseBase[None], status_code=status.HTTP_200_OK)
async def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete (deactivate) a prompt template.
    """
    prompt_service = PromptService(db)
    template = prompt_service.get_template_by_id(str(template_id))
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    db.delete(template)
    db.commit()
    return ResponseBase(success=True, message="Template deleted successfully", data=None)
