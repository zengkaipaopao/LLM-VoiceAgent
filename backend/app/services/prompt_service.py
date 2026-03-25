"""
Prompt template service.

Manages prompt templates for different scenarios.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate


class PromptService:
    """Service for managing prompt templates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_template(self, code: str) -> Optional[PromptTemplate]:
        stmt = select(PromptTemplate).where(
            PromptTemplate.code == code,
            PromptTemplate.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_template_by_id(self, template_id: str) -> Optional[PromptTemplate]:
        stmt = select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PromptTemplate]:
        stmt = select(PromptTemplate)

        if active_only:
            stmt = stmt.where(PromptTemplate.is_active.is_(True))

        if category:
            stmt = stmt.where(PromptTemplate.category == category)

        stmt = stmt.order_by(PromptTemplate.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def render_prompt(
        self,
        template: PromptTemplate,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt = template.system_prompt

        if variables:
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                prompt = prompt.replace(placeholder, str(value))

        return prompt

    async def create_template(
        self,
        name: str,
        code: str,
        system_prompt: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        extraction_prompt: Optional[str] = None,
        extraction_schema: Optional[Dict] = None,
        **kwargs,
    ) -> PromptTemplate:
        template = PromptTemplate(
            name=name,
            code=code,
            system_prompt=system_prompt,
            category=category,
            description=description,
            extraction_prompt=extraction_prompt,
            extraction_schema=extraction_schema,
            **kwargs,
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template
