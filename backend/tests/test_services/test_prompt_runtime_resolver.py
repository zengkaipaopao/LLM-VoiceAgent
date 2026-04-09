from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.model_defaults import require_generate_model
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateUpdate
from app.services.prompt_runtime_resolver import resolve_prompt_runtime


@pytest.mark.asyncio
async def test_resolve_prompt_runtime_uses_template_values_and_renders_current_time():
    template = SimpleNamespace(
        code="base_appointment",
        name="Base Appointment",
        system_prompt="raw system prompt",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
    )
    prompt_service = SimpleNamespace(
        get_template=AsyncMock(return_value=template),
        render_prompt=Mock(return_value="rendered prompt with current time"),
    )

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code="base_appointment",
        default_code="base_appointment",
        render_system_instruction=True,
    )

    assert runtime.template is template
    assert runtime.template_code == "base_appointment"
    assert runtime.system_instruction == "rendered prompt with current time"
    assert runtime.llm_provider == "gemini"
    assert runtime.llm_model == "gemini-2.5-flash"
    assert runtime.temperature == 0.4
    assert runtime.max_tokens == 512
    assert runtime.voice_id == "Aoede"
    assert runtime.notice == "Loaded prompt template: Base Appointment (base_appointment)"


@pytest.mark.asyncio
async def test_resolve_prompt_runtime_returns_fallback_instruction_when_template_missing():
    prompt_service = SimpleNamespace(
        get_template=AsyncMock(return_value=None),
        render_prompt=Mock(),
    )

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code="missing_prompt",
        default_code="missing_prompt",
        fallback_instruction="fallback system instruction",
        missing_notice="missing template notice",
    )

    assert runtime.template is None
    assert runtime.template_code == "missing_prompt"
    assert runtime.system_instruction == "fallback system instruction"
    assert runtime.voice_id is None
    assert runtime.notice == "missing template notice"


@pytest.mark.asyncio
async def test_resolve_prompt_runtime_preserves_template_model_for_generate_usage():
    template = SimpleNamespace(
        code="base_appointment",
        name="Base Appointment",
        system_prompt="raw system prompt",
        llm_provider="gemini",
        llm_model="gemini-3.1-flash-live-preview",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
    )
    prompt_service = SimpleNamespace(
        get_template=AsyncMock(return_value=template),
        render_prompt=Mock(return_value="rendered prompt with current time"),
    )

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code="base_appointment",
        default_code="base_appointment",
        model_capability="generate",
    )

    assert runtime.llm_model == "gemini-3.1-flash-live-preview"


@pytest.mark.asyncio
async def test_resolve_prompt_runtime_preserves_template_model_for_live_usage():
    template = SimpleNamespace(
        code="base_appointment",
        name="Base Appointment",
        system_prompt="raw system prompt",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
    )
    prompt_service = SimpleNamespace(
        get_template=AsyncMock(return_value=template),
        render_prompt=Mock(return_value="rendered prompt with current time"),
    )

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code="base_appointment",
        default_code="base_appointment",
        model_capability="live",
    )

    assert runtime.llm_model == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_resolve_prompt_runtime_normalizes_provider_prefixed_model_reference():
    template = SimpleNamespace(
        code="base_appointment",
        name="Base Appointment",
        system_prompt="raw system prompt",
        llm_provider=None,
        llm_model="gemini/gemini-2.5-flash-lite",
        temperature=0.4,
        max_tokens=512,
        voice_id="Aoede",
    )
    prompt_service = SimpleNamespace(
        get_template=AsyncMock(return_value=template),
        render_prompt=Mock(return_value="rendered prompt with current time"),
    )

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code="base_appointment",
        default_code="base_appointment",
        model_capability="generate",
    )

    assert runtime.llm_provider == "gemini"
    assert runtime.llm_model == "gemini-2.5-flash-lite"


def test_require_generate_model_strips_provider_prefix():
    assert require_generate_model("gemini/gemini-2.5-flash-lite", source="Prompt llm_model") == "gemini-2.5-flash-lite"


def test_prompt_template_schema_normalizes_provider_prefixed_model_reference():
    created = PromptTemplateCreate(
        name="Base Appointment",
        code="base_appointment",
        system_prompt="hello",
        llm_provider="gemini",
        llm_model="gemini/gemini-2.5-flash-lite",
    )
    updated = PromptTemplateUpdate(
        llm_model="gemini/gemini-2.5-flash-lite",
    )

    assert created.llm_provider == "gemini"
    assert created.llm_model == "gemini-2.5-flash-lite"
    assert updated.llm_provider == "gemini"
    assert updated.llm_model == "gemini-2.5-flash-lite"
