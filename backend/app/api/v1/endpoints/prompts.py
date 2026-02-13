"""
Prompt templates API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
# Use new schemas
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse
)
from app.services.prompt_service import PromptService

router = APIRouter()


@router.get("", response_model=PromptTemplateListResponse)
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
    
    return PromptTemplateListResponse(
        templates=[PromptTemplateResponse.from_orm(t) for t in templates],
        total=len(templates)
    )


@router.get("/{template_id}", response_model=PromptTemplateResponse)
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
    
    return PromptTemplateResponse.from_orm(template)


@router.get("/code/{code}", response_model=PromptTemplateResponse)
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
    
    return PromptTemplateResponse.from_orm(template)


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
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
    # Since PromptService.create_template accepts kwargs, we can unpack dict
    template = prompt_service.create_template(
        **template_in.dict()
    )
    
    return PromptTemplateResponse.from_orm(template)


@router.put("/{template_id}", response_model=PromptTemplateResponse)
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
    
    # Update fields
    # We need to implement update in service or do it here
    # For now, let's do it here or add method to service
    
    update_data = template_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return PromptTemplateResponse.from_orm(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
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
    
    # Hard delete or soft delete? 
    # Logic in service usually. Let's implementing delete here or in service.
    # Given 'is_active' exists, maybe soft delete via update?
    # But this is DELETE method.
    
    db.delete(template)
    db.commit()
    return None
