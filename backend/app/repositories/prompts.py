from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.repositories.base import JsonFileRepository
from app.schemas.prompts import PromptCapabilities, PromptCreate, PromptTemplate, PromptUpdate, VoiceConfig


class PromptRepository(JsonFileRepository):
    @staticmethod
    def _split_lines(value: str | None) -> list[str]:
        if not value:
            return []
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.split("\n")

    def _prepare_storage(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        for item in items:
            stored_item = dict(item)
            system_prompt = stored_item.get("system_prompt") or ""
            stored_item["system_prompt_lines"] = self._split_lines(system_prompt)
            stored_item.pop("system_prompt", None)
            stored.append(stored_item)
        return stored

    def _hydrate_prompts(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            lines = item.get("system_prompt_lines")
            if isinstance(lines, list) and lines:
                item["system_prompt"] = "\n".join(lines)
            elif "system_prompt" in item:
                item["system_prompt"] = item["system_prompt"] or ""
                item["system_prompt_lines"] = self._split_lines(item["system_prompt"])
            else:
                item["system_prompt"] = ""
                item["system_prompt_lines"] = []

    def __init__(self, data_file: Path | None = None) -> None:
        super().__init__("prompts.json", data_file=data_file)

    def list(self) -> list[PromptTemplate]:
        items = self._read_json()
        self._hydrate_prompts(items)
        updated = False
        for item in items:
            if "capabilities" not in item:
                appointment = item.pop("enable_appointment_logging", False)
                capabilities = PromptCapabilities(appointment_logging=appointment)
                item["capabilities"] = capabilities.model_dump()
                updated = True
            else:
                capabilities = PromptCapabilities(**item["capabilities"])
                normalized = capabilities.model_dump()
                if normalized != item["capabilities"]:
                    item["capabilities"] = normalized
                    updated = True
        if updated:
            self._write_json(self._prepare_storage(items))
        return [PromptTemplate(**item) for item in items]

    def create(self, payload: PromptCreate) -> PromptTemplate:
        with self._lock:
            items = self._read_json()
            self._hydrate_prompts(items)
            prompt_id = f"prompt_{uuid4().hex[:8]}"
            now = datetime.utcnow().isoformat()
            if isinstance(payload.capabilities, PromptCapabilities):
                capabilities = payload.capabilities.model_dump()
            elif payload.capabilities:
                capabilities = payload.capabilities
            else:
                capabilities = PromptCapabilities().model_dump()
            record: dict[str, Any] = {
                "id": prompt_id,
                "name": payload.name,
                "model_id": payload.model_id,
                "system_prompt": payload.system_prompt,
                "welcome_message": payload.welcome_message,
                "closing_message": payload.closing_message,
                "voice_config": payload.voice_config.model_dump(exclude_none=True)
                if isinstance(payload.voice_config, VoiceConfig)
                else payload.voice_config,
                "version": payload.version,
                "updated_at": now,
                "capabilities": capabilities,
            }
            items.append(record)
            self._write_json(self._prepare_storage(items))
        return PromptTemplate(**record)

    def update(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        with self._lock:
            items = self._read_json()
            self._hydrate_prompts(items)
            target = next((item for item in items if item["id"] == prompt_id), None)
            if not target:
                raise KeyError(prompt_id)
            if payload.name is not None:
                target["name"] = payload.name
            if payload.model_id is not None:
                target["model_id"] = payload.model_id
            if payload.system_prompt is not None:
                target["system_prompt"] = payload.system_prompt
            if payload.welcome_message is not None:
                target["welcome_message"] = payload.welcome_message
            if payload.closing_message is not None:
                target["closing_message"] = payload.closing_message
            if payload.voice_config is not None:
                if isinstance(payload.voice_config, VoiceConfig):
                    target["voice_config"] = payload.voice_config.model_dump(exclude_none=True)
                else:
                    target["voice_config"] = payload.voice_config
            if payload.version is not None:
                target["version"] = payload.version
            if payload.capabilities is not None:
                if isinstance(payload.capabilities, PromptCapabilities):
                    target["capabilities"] = payload.capabilities.model_dump()
                else:
                    target["capabilities"] = PromptCapabilities(**payload.capabilities).model_dump()
            target["updated_at"] = datetime.utcnow().isoformat()
            self._write_json(self._prepare_storage(items))
        return PromptTemplate(**target)

    def delete(self, prompt_id: str) -> None:
        with self._lock:
            items = self._read_json()
            filtered = [item for item in items if item["id"] != prompt_id]
            if len(filtered) == len(items):
                raise KeyError(prompt_id)
            self._write_json(filtered)


prompt_repository = PromptRepository()
