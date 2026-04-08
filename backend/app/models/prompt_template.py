"""
Prompt template model for database.
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.core.model_defaults import DEFAULT_GENERATE_MODEL
from app.models.base import Base, TimestampMixin


class PromptTemplate(Base, TimestampMixin):
    """
    Prompt template model for managing LLM prompts.
    
    Supports multiple scenarios (hotel booking, flight booking, etc.)
    """
    __tablename__ = "prompt_templates"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(255), nullable=False)  # "酒店预订助手"
    code = Column(String(100), unique=True, nullable=False, index=True)  # "hotel_booking"
    description = Column(Text)
    category = Column(String(50), index=True)  # "booking", "customer_service"
    
    # Template content
    system_prompt = Column(Text, nullable=False)  # System prompt for LLM
    extraction_prompt = Column(Text)  # Prompt for extracting structured data
    
    # Configuration
    variables = Column(JSONB)  # Variable definitions
    example_conversations = Column(JSONB)  # Example conversations
    extraction_schema = Column(JSONB)  # JSON schema for extraction
    
    # Output Configuration
    response_format = Column(String(50), default="text")  # "text" or "json_object"
    output_schema = Column(JSONB)  # JSON schema for output validation
    
    # LLM Configuration
    llm_provider = Column(String(50), default="gemini")
    llm_model = Column(String(100), default=DEFAULT_GENERATE_MODEL)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    
    # Voice Configuration
    voice_provider = Column(String(50))
    voice_id = Column(String(100))
    voice_settings = Column(JSONB)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    version = Column(Integer, default=1)
    
    # Metadata
    created_by = Column(String(255))
    
    def __repr__(self):
        return f"<PromptTemplate {self.code} - {self.name}>"
