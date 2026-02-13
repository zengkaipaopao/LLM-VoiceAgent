"""
Prompt Template Pydantic schemas.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class PromptTemplateBase(BaseModel):
    """Base prompt template schema."""
    name: str = Field(..., description="Template name")
    code: str = Field(..., description="Unique code")
    description: Optional[str] = Field(None, description="Description")
    category: Optional[str] = Field(None, description="Category (booking, support, etc.)")
    
    # Template Content
    system_prompt: str = Field(..., description="System prompt")
    extraction_prompt: Optional[str] = Field(None, description="Extraction prompt")
    extraction_schema: Optional[Dict[str, Any]] = Field(None, description="Extraction JSON schema")
    
    # Output Configuration
    response_format: Optional[str] = Field("text", description="Response format: text or json_object")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Output JSON schema")
    
    # LLM Configuration
    llm_provider: Optional[str] = Field("gemini", description="LLM provider (gemini, openai, etc.)")
    llm_model: Optional[str] = Field("gemini-2.0-flash", description="LLM model name")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(2048, description="Max tokens")
    
    # Voice Configuration
    voice_provider: Optional[str] = Field(None, description="Voice provider")
    voice_id: Optional[str] = Field(None, description="Voice ID")
    voice_settings: Optional[Dict[str, Any]] = Field(None, description="Voice settings")
    
    # Other
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables")
    example_conversations: Optional[List[Dict[str, Any]]] = Field(None, description="Example conversations")
    is_active: bool = Field(True, description="Is active")


class PromptTemplateCreate(PromptTemplateBase):
    """Schema for creating a prompt template."""
    pass


class PromptTemplateUpdate(BaseModel):
    """Schema for updating a prompt template."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    extraction_prompt: Optional[str] = None
    extraction_schema: Optional[Dict[str, Any]] = None
    
    response_format: Optional[str] = None
    output_schema: Optional[Dict[str, Any]] = None
    
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    
    variables: Optional[Dict[str, Any]] = None
    example_conversations: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


class PromptTemplateResponse(PromptTemplateBase):
    """Response schema for prompt template."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    version: int
    
    class Config:
        from_attributes = True


class PromptTemplateListResponse(BaseModel):
    """List response for prompt templates."""
    templates: List[PromptTemplateResponse]
    total: int
