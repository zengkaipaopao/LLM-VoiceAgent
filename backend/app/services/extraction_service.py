"""
Appointment extraction service.

Extracts structured appointment data from LLM conversations.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.llm import BaseLLMService
from app.models.prompt_template import PromptTemplate


class AppointmentExtraction(BaseModel):
    """Extracted appointment data."""
    caller_name: Optional[str] = Field(None, description="Caller name")
    company: Optional[str] = Field(None, description="Company name")
    appointment_time: Optional[str] = Field(None, description="Appointment time (ISO 8601)")
    appointment_content: str = Field(..., description="Appointment content")
    category: Optional[str] = Field(None, description="Category")
    summary: str = Field(..., description="Summary")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw extracted data")


class ExtractionService:
    """Service for extracting appointment information from conversations."""
    
    def __init__(self, llm_service: BaseLLMService):
        """
        Initialize extraction service.
        
        Args:
            llm_service: LLM service instance
        """
        self.llm = llm_service
    
    async def extract_appointment(
        self,
        conversation: List[Dict[str, str]],
        template: PromptTemplate,
        variables: Optional[Dict[str, Any]] = None
    ) -> AppointmentExtraction:
        """
        Extract appointment information from conversation.
        
        Args:
            conversation: List of conversation messages
            template: Prompt template for extraction
            variables: Optional variables for template rendering
            
        Returns:
            Extracted appointment data
        """
        # Build extraction prompt
        extraction_prompt = self._build_extraction_prompt(
            conversation,
            template,
            variables or {}
        )
        
        # Call LLM for extraction
        messages = [
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": "请提取预约信息"}
        ]
        
        try:
            # Get JSON response from LLM
            result = await self.llm.chat_with_json(
                messages=messages,
                schema=template.extraction_schema,
                temperature=0.3  # Lower temperature for more consistent extraction
            )
            
            # Parse and validate result
            return self._parse_extraction_result(result, template)
            
        except Exception as e:
            # If extraction fails, return low confidence result
            return AppointmentExtraction(
                appointment_content="提取失败",
                summary=f"无法从对话中提取预约信息: {str(e)}",
                confidence=0.0,
                raw_data={"error": str(e)}
            )
    
    def _build_extraction_prompt(
        self,
        conversation: List[Dict[str, str]],
        template: PromptTemplate,
        variables: Dict[str, Any]
    ) -> str:
        """Build extraction prompt from template."""
        # Format conversation
        conversation_text = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in conversation
        ])
        
        # Add conversation to variables
        variables["conversation"] = conversation_text
        variables["current_time"] = datetime.now().isoformat()
        
        # Render template
        prompt = template.extraction_prompt or template.system_prompt
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))
        
        return prompt
    
    def _parse_extraction_result(
        self,
        result: Dict[str, Any],
        template: PromptTemplate
    ) -> AppointmentExtraction:
        """Parse LLM extraction result into AppointmentExtraction."""
        
        # Extract common fields
        caller_name = result.get("caller_name") or result.get("guest_name") or result.get("passenger_name")
        company = result.get("company")
        
        # Handle different time field names
        appointment_time = (
            result.get("appointment_time") or 
            result.get("check_in_date") or 
            result.get("departure_date")
        )
        
        # Build appointment content
        appointment_content = result.get("appointment_content", "")
        if not appointment_content:
            # Try to build from other fields
            if result.get("room_type"):
                appointment_content = f"{result.get('room_type')}房间预订"
            elif result.get("cabin_class"):
                appointment_content = f"{result.get('cabin_class')}机票预订"
            else:
                appointment_content = "预约"
        
        category = result.get("category", template.category)
        summary = result.get("summary", appointment_content)
        confidence = float(result.get("confidence", 0.8))
        
        return AppointmentExtraction(
            caller_name=caller_name,
            company=company,
            appointment_time=appointment_time,
            appointment_content=appointment_content,
            category=category,
            summary=summary,
            confidence=confidence,
            raw_data=result
        )
