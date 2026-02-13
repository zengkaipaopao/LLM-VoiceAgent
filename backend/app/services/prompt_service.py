"""
Prompt template service.

Manages prompt templates for different scenarios.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate


class PromptService:
    """Service for managing prompt templates."""
    
    def __init__(self, db: Session):
        """
        Initialize prompt service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_template(self, code: str) -> Optional[PromptTemplate]:
        """
        Get template by code.
        
        Args:
            code: Template code (e.g., 'hotel_booking')
            
        Returns:
            Template if found, None otherwise
        """
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.code == code,
            PromptTemplate.is_active == True
        ).first()
    
    def get_template_by_id(self, template_id: str) -> Optional[PromptTemplate]:
        """
        Get template by ID.
        
        Args:
            template_id: Template UUID
            
        Returns:
            Template if found, None otherwise
        """
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.id == template_id,
            PromptTemplate.is_active == True
        ).first()
    
    def list_templates(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[PromptTemplate]:
        """
        List all templates.
        
        Args:
            category: Filter by category (optional)
            active_only: Only return active templates
            
        Returns:
            List of templates
        """
        query = self.db.query(PromptTemplate)
        
        if active_only:
            query = query.filter(PromptTemplate.is_active == True)
        
        if category:
            query = query.filter(PromptTemplate.category == category)
        
        return query.order_by(PromptTemplate.name).all()
    
    def render_prompt(
        self,
        template: PromptTemplate,
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render prompt with variables.
        
        Args:
            template: Prompt template
            variables: Variables to substitute
            
        Returns:
            Rendered prompt
        """
        prompt = template.system_prompt
        
        if variables:
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                prompt = prompt.replace(placeholder, str(value))
        
        return prompt
    
    def create_template(
        self,
        name: str,
        code: str,
        system_prompt: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        extraction_prompt: Optional[str] = None,
        extraction_schema: Optional[Dict] = None,
        **kwargs
    ) -> PromptTemplate:
        """
        Create a new template.
        
        Args:
            name: Template name
            code: Unique code
            system_prompt: System prompt text
            category: Category
            description: Description
            extraction_prompt: Extraction prompt
            extraction_schema: JSON schema for extraction
            **kwargs: Additional fields
            
        Returns:
            Created template
        """
        template = PromptTemplate(
            name=name,
            code=code,
            system_prompt=system_prompt,
            category=category,
            description=description,
            extraction_prompt=extraction_prompt,
            extraction_schema=extraction_schema,
            **kwargs
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
