"""
Chat API schemas.
"""
from pydantic import BaseModel, Field, ConfigDict
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


class TestSessionStartRequest(BaseModel):
    """Request to create a unified test session."""
    template_code: str = Field(default="general_appointment", description="Prompt template code")
    provider: Optional[str] = Field(None, description="LLM provider override")
    model: Optional[str] = Field(None, description="LLM model override")
    caller_name: Optional[str] = Field(None, description="Simulated caller name")
    mode: str = Field(default="text", description="Test mode: text or voice")


class TestSessionStartResponse(BaseModel):
    """Response returned after creating a test session."""
    call_id: UUID = Field(..., description="Created call ID")
    simulated_phone: str = Field(..., description="Generated simulated phone number")
    started_at: datetime = Field(..., description="Session start time")
    template_code: str = Field(..., description="Bound prompt template code")
    llm_provider: str = Field(..., description="LLM provider in use")
    llm_model: str = Field(..., description="LLM model in use")


class TestSessionFinalizeRequest(BaseModel):
    """Request to finalize a test session."""
    call_id: UUID = Field(..., description="Call ID to finalize")
    template_code: Optional[str] = Field(None, description="Template code override for extraction")
    run_extraction: bool = Field(True, description="Whether to run extraction on finalize")


class TestSessionFinalizeResponse(BaseModel):
    """Response returned after finalizing a test session."""
    call_id: UUID = Field(..., description="Finalized call ID")
    status: str = Field(..., description="Final call status")
    ended_at: datetime = Field(..., description="Session end time")
    duration_seconds: int = Field(..., description="Computed call duration")
    appointment_id: Optional[UUID] = Field(None, description="Created or existing appointment ID")
    extraction: Optional[ExtractionResponse] = Field(None, description="Extraction details")
    already_extracted: bool = Field(False, description="Whether appointment already existed")


class TestSessionAppendMessagesRequest(BaseModel):
    """Append normalized conversation messages to an existing test session."""
    call_id: UUID = Field(..., description="Call ID to update")
    template_code: Optional[str] = Field(None, description="Template code bound to the test session")
    provider: Optional[str] = Field(None, description="LLM provider in use")
    model: Optional[str] = Field(None, description="LLM model in use")
    messages: List[ChatMessage] = Field(default_factory=list, description="Messages to append")


class TestSessionAppendMessagesResponse(BaseModel):
    """Result returned after appending messages to a test session."""
    call_id: UUID = Field(..., description="Updated call ID")
    appended_count: int = Field(..., description="Number of messages appended")
    transcript_length: int = Field(..., description="Current transcript character length")


class TestSessionOperationTurnRequest(BaseModel):
    """Advance test session through ChatService operation flow without generic LLM fallback."""
    call_id: UUID = Field(..., description="Call ID to update")
    message: str = Field(..., description="Latest finalized user utterance")
    template_code: Optional[str] = Field(None, description="Template code bound to the test session")
    provider: Optional[str] = Field(None, description="LLM provider in use")
    model: Optional[str] = Field(None, description="LLM model in use")


class TestSessionOperationTurnResponse(BaseModel):
    """Result returned after attempting to advance the operation flow."""
    call_id: UUID = Field(..., description="Updated call ID")
    handled: bool = Field(..., description="Whether ChatService operation flow handled this turn")
    response: Optional[str] = Field(None, description="Deterministic assistant reply from operation flow")
    operation: Optional[str] = Field(None, description="Current operation type: update or cancel")
    state_status: Optional[str] = Field(None, description="Current operation flow state")
    executed: bool = Field(False, description="Whether this turn executed the operation")


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
    
    model_config = ConfigDict(from_attributes=True)


class PromptTemplateListResponse(BaseModel):
    """List of prompt templates."""
    templates: List[PromptTemplateResponse]
    total: int
