"""
Chat API schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request for chat completion."""
    message: str = Field(..., description="User message")
    template_code: str = Field(default="general_appointment", description="Prompt template code")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model name (optional)")
    call_id: Optional[UUID] = Field(None, description="Associated call ID")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")


class ChatResponse(BaseModel):
    """Response from chat completion."""
    response: str = Field(..., description="AI response")
    call_id: UUID = Field(..., description="Call ID")
    tokens_used: Optional[int] = Field(None, description="Tokens used")


class ExtractionRequest(BaseModel):
    """Request for appointment extraction."""
    call_id: UUID = Field(..., description="Call ID to extract from")
    template_code: Optional[str] = Field(None, description="Template code for extraction")


class ExtractionResponse(BaseModel):
    """Response from appointment extraction."""
    success: bool = Field(..., description="Whether extraction succeeded")
    appointment_id: Optional[UUID] = Field(None, description="Created appointment ID")
    extracted_data: Dict[str, Any] = Field(..., description="Extracted data")
    confidence: float = Field(..., description="Extraction confidence")
    message: str = Field(..., description="Status message")


class PromptTemplateResponse(BaseModel):
    """Prompt template response."""
    id: UUID
    name: str
    code: str
    description: Optional[str]
    category: Optional[str]
    system_prompt: str
    extraction_schema: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PromptTemplateListResponse(BaseModel):
    """List of prompt templates."""
    templates: List[PromptTemplateResponse]
    total: int
