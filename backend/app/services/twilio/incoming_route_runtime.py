from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.exceptions import BusinessException
from app.services.prompt_runtime_resolver import PromptRuntimeConfig
from app.services.prompt_service import PromptService
from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_prompt_code_token,
)

OFFICIAL_DEMO_TEMPLATE_CODE = "official_demo_baseline"


def is_official_demo_route(route_value: str | None) -> bool:
    return (route_value or "").strip().lower() == "official_demo_live"


def is_official_conversational_agents_route(route_value: str | None) -> bool:
    return (route_value or "").strip().lower() == "official_conversational_agents"


def build_official_demo_runtime() -> PromptRuntimeConfig:
    system_instruction = (settings.twilio_official_demo_instruction or "").strip()
    if not system_instruction:
        raise BusinessException(
            "TWILIO_OFFICIAL_DEMO_INSTRUCTION is required for the official baseline demo route."
        )

    configured_model = (settings.twilio_official_demo_model or settings.default_live_model).strip()
    if not configured_model:
        raise BusinessException(
            "TWILIO_OFFICIAL_DEMO_MODEL or DEFAULT_LIVE_MODEL must be configured."
        )

    configured_voice = (
        settings.twilio_official_demo_voice
        or settings.default_live_voice
        or "Aoede"
    ).strip() or "Aoede"

    return PromptRuntimeConfig(
        template=None,
        template_code=OFFICIAL_DEMO_TEMPLATE_CODE,
        template_name="Official Demo Baseline",
        system_instruction=system_instruction,
        llm_provider="gemini",
        llm_model=configured_model,
        temperature=float(settings.llm_temperature),
        max_tokens=int(settings.llm_max_tokens),
        voice_provider="gemini",
        voice_id=configured_voice,
        notice="Loaded official baseline Twilio demo runtime.",
    )


async def resolve_twilio_incoming_prompt_code(
    *,
    db: AsyncSession,
    prompt_code: str | None,
    to_number: str | None,
) -> str | None:
    from_request = _normalize_prompt_code_token(prompt_code)
    if from_request:
        return from_request

    prompt_service = PromptService(db)
    normalized_to = _normalize_e164_number(to_number)
    if normalized_to:
        template = await prompt_service.find_template_by_twilio_inbound_number(normalized_to)
        if template:
            return template.code
        mapped = _normalize_prompt_code_token(settings.twilio_incoming_prompt_mapping.get(normalized_to))
        if mapped:
            return mapped

    default_template = await prompt_service.get_twilio_incoming_default_template()
    if default_template:
        return default_template.code

    return _normalize_prompt_code_token(settings.twilio_default_prompt_code)
