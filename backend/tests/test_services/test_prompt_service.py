from types import SimpleNamespace

import pytest

from app.services.prompt_service import PromptService, normalize_twilio_inbound_numbers


def test_normalize_twilio_inbound_numbers_filters_invalid_and_deduplicates():
    assert normalize_twilio_inbound_numbers(
        [" +815012345678 ", "+815012345678", "invalid", "", "+819012345678"]
    ) == ["+815012345678", "+819012345678"]


@pytest.mark.asyncio
async def test_validate_twilio_inbound_numbers_rejects_conflicts():
    service = PromptService(db=None)  # type: ignore[arg-type]
    async def _list_templates(active_only=True, category=None):
        return [
        SimpleNamespace(
            id="other-id",
            code="base_appointment",
            twilio_inbound_numbers=["+815012345678"],
        )
        ]
    service.list_templates = _list_templates  # type: ignore[assignment]

    with pytest.raises(ValueError, match=r"\+815012345678 -> base_appointment"):
        await service.validate_twilio_inbound_numbers(numbers=["+815012345678"])


@pytest.mark.asyncio
async def test_find_template_by_twilio_inbound_number_matches_assigned_number():
    service = PromptService(db=None)  # type: ignore[arg-type]
    target = SimpleNamespace(
        id="target-id",
        code="base_appointment",
        twilio_inbound_numbers=["+815012345678", "+819012345678"],
    )
    async def _list_templates(active_only=True, category=None):
        return [target]
    service.list_templates = _list_templates  # type: ignore[assignment]

    matched = await service.find_template_by_twilio_inbound_number("+819012345678")

    assert matched is target
