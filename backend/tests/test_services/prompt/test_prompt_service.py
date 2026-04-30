from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.prompt_service import PromptService, normalize_twilio_inbound_numbers


class FakePromptDb:
    def __init__(self) -> None:
        self.deleted = None
        self.committed = False
        self.refreshed = None

    async def delete(self, item):
        self.deleted = item

    async def commit(self):
        self.committed = True

    async def refresh(self, item):
        self.refreshed = item


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


@pytest.mark.asyncio
async def test_create_template_checked_rejects_duplicate_active_code():
    service = PromptService(db=None)  # type: ignore[arg-type]
    service.get_template = AsyncMock(return_value=SimpleNamespace(code="base_appointment"))  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="already exists"):
        await service.create_template_checked({"code": "base_appointment"})


@pytest.mark.asyncio
async def test_update_template_validates_twilio_numbers_and_persists():
    db = FakePromptDb()
    service = PromptService(db=db)  # type: ignore[arg-type]
    template = SimpleNamespace(
        id="template-id",
        code="base_appointment",
        is_active=True,
        is_twilio_incoming_default=False,
        twilio_inbound_numbers=[],
    )
    service.get_template_by_id = AsyncMock(return_value=template)  # type: ignore[method-assign]
    service.validate_twilio_inbound_numbers = AsyncMock(return_value=["+815012345678"])  # type: ignore[method-assign]

    updated = await service.update_template(
        "template-id",
        {"name": "Updated", "twilio_inbound_numbers": ["+815012345678"]},
    )

    assert updated is template
    assert template.name == "Updated"
    assert template.twilio_inbound_numbers == ["+815012345678"]
    assert db.committed is True
    assert db.refreshed is template


@pytest.mark.asyncio
async def test_delete_template_returns_false_when_missing():
    service = PromptService(db=FakePromptDb())  # type: ignore[arg-type]
    service.get_template_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    assert await service.delete_template("missing-id") is False


@pytest.mark.asyncio
async def test_delete_template_deletes_and_commits():
    db = FakePromptDb()
    service = PromptService(db=db)  # type: ignore[arg-type]
    template = SimpleNamespace(id="template-id")
    service.get_template_by_id = AsyncMock(return_value=template)  # type: ignore[method-assign]

    assert await service.delete_template("template-id") is True
    assert db.deleted is template
    assert db.committed is True
