"""
Prompt template service.

Manages prompt templates for different scenarios.
"""
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate

_TWILIO_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_twilio_inbound_numbers(numbers: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for raw in numbers or []:
        candidate = str(raw or "").strip()
        if not candidate or not _TWILIO_E164_PATTERN.fullmatch(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


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

    async def find_template_by_twilio_inbound_number(self, number: str | None) -> Optional[PromptTemplate]:
        candidate = str(number or "").strip()
        if not candidate:
            return None

        templates = await self.list_templates(active_only=True)
        for template in templates:
            assigned = normalize_twilio_inbound_numbers(
                getattr(template, "twilio_inbound_numbers", None)
            )
            if candidate in assigned:
                return template
        return None

    async def get_twilio_incoming_default_template(self) -> Optional[PromptTemplate]:
        stmt = (
            select(PromptTemplate)
            .where(
                PromptTemplate.is_active.is_(True),
                PromptTemplate.is_twilio_incoming_default.is_(True),
            )
            .order_by(PromptTemplate.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def validate_twilio_inbound_numbers(
        self,
        *,
        numbers: Optional[List[str]],
        exclude_template_id: str | None = None,
    ) -> List[str]:
        normalized = normalize_twilio_inbound_numbers(numbers)
        if not normalized:
            return []

        templates = await self.list_templates(active_only=True)
        conflicts: dict[str, str] = {}
        for template in templates:
            template_id = str(template.id)
            if exclude_template_id and template_id == exclude_template_id:
                continue
            assigned = normalize_twilio_inbound_numbers(
                getattr(template, "twilio_inbound_numbers", None)
            )
            for number in assigned:
                conflicts[number] = template.code

        duplicates = [number for number in normalized if number in conflicts]
        if duplicates:
            conflict_details = ", ".join(f"{number} -> {conflicts[number]}" for number in duplicates)
            raise ValueError(f"Twilio inbound numbers already assigned: {conflict_details}")

        return normalized

    async def sync_twilio_incoming_default(self, template: PromptTemplate) -> None:
        if not template.is_active:
            template.is_twilio_incoming_default = False
            return

        if not template.is_twilio_incoming_default:
            return

        stmt = (
            update(PromptTemplate)
            .where(
                PromptTemplate.id != template.id,
                PromptTemplate.is_twilio_incoming_default.is_(True),
            )
            .values(is_twilio_incoming_default=False)
        )
        await self.db.execute(stmt)

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

        template.twilio_inbound_numbers = normalize_twilio_inbound_numbers(
            getattr(template, "twilio_inbound_numbers", None)
        )
        await self.validate_twilio_inbound_numbers(numbers=template.twilio_inbound_numbers)

        self.db.add(template)
        await self.db.flush()
        await self.sync_twilio_incoming_default(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    async def create_template_checked(self, template_data: dict[str, Any]) -> PromptTemplate:
        code = str(template_data.get("code") or "")
        if await self.get_template(code):
            raise ValueError(f"Template code '{code}' already exists")
        return await self.create_template(**template_data)

    async def update_template(self, template_id: str, update_data: dict[str, Any]) -> Optional[PromptTemplate]:
        template = await self.get_template_by_id(template_id)
        if not template:
            return None

        if "twilio_inbound_numbers" in update_data:
            update_data["twilio_inbound_numbers"] = await self.validate_twilio_inbound_numbers(
                numbers=update_data["twilio_inbound_numbers"],
                exclude_template_id=str(template.id),
            )

        for field, value in update_data.items():
            setattr(template, field, value)

        await self.sync_twilio_incoming_default(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: str) -> bool:
        template = await self.get_template_by_id(template_id)
        if not template:
            return False

        await self.db.delete(template)
        await self.db.commit()
        return True
