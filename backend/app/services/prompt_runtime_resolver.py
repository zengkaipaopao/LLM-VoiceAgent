"""
Shared prompt runtime resolution helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.core.model_defaults import resolve_generate_model, resolve_live_model
from app.services.prompt_service import PromptService
from app.utils.datetime_utils import now_tokyo_naive


@dataclass
class PromptRuntimeConfig:
    template: Any | None
    template_code: str
    template_name: str | None
    system_instruction: str | None
    llm_provider: str | None
    llm_model: str | None
    temperature: float
    max_tokens: int
    voice_id: str | None
    notice: str | None


def _resolve_runtime_model(candidate_model: str | None, *, model_capability: Literal["any", "generate", "live"]) -> str:
    if model_capability == "generate":
        return resolve_generate_model(candidate_model, fallback_model=settings.default_llm_model)
    if model_capability == "live":
        return resolve_live_model(candidate_model, fallback_model=settings.default_live_model)

    token = (candidate_model or "").strip()
    if token:
        return token
    return resolve_generate_model(None, fallback_model=settings.default_llm_model)


async def resolve_prompt_runtime(
    prompt_service: PromptService,
    *,
    template_code: str | None,
    default_code: str = "general_appointment",
    fallback_code: str | None = None,
    render_system_instruction: bool = False,
    fallback_instruction: str | None = None,
    missing_notice: str | None = None,
    model_capability: Literal["any", "generate", "live"] = "any",
) -> PromptRuntimeConfig:
    requested_code = (template_code or "").strip() or default_code
    normalized_fallback = (fallback_code or "").strip() or None

    template = await prompt_service.get_template(requested_code) if requested_code else None
    if not template and normalized_fallback and requested_code != normalized_fallback:
        template = await prompt_service.get_template(normalized_fallback)

    if template:
        system_instruction = (
            prompt_service.render_prompt(
                template,
                {"current_time": now_tokyo_naive().isoformat()},
            )
            if render_system_instruction
            else ((template.system_prompt or "").strip() or fallback_instruction)
        )
        template_model = (template.llm_model or "").strip()
        llm_model = template_model or _resolve_runtime_model(None, model_capability=model_capability)
        return PromptRuntimeConfig(
            template=template,
            template_code=(template.code or requested_code).strip(),
            template_name=(template.name or "").strip() or None,
            system_instruction=system_instruction,
            llm_provider=(template.llm_provider or "").strip() or None,
            llm_model=llm_model,
            temperature=float(
                template.temperature if template.temperature is not None else settings.llm_temperature
            ),
            max_tokens=int(template.max_tokens or settings.llm_max_tokens),
            voice_id=(template.voice_id or "").strip() or None,
            notice=f"Loaded prompt template: {template.name} ({template.code})",
        )

    return PromptRuntimeConfig(
        template=None,
        template_code=requested_code,
        template_name=None,
        system_instruction=fallback_instruction,
        llm_provider=None,
        llm_model=_resolve_runtime_model(None, model_capability=model_capability),
        temperature=float(settings.llm_temperature),
        max_tokens=int(settings.llm_max_tokens),
        voice_id=None,
        notice=missing_notice or f"Prompt template '{requested_code}' not found or inactive.",
    )
