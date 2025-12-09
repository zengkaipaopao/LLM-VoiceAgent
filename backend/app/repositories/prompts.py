from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.repositories.base import JsonFileRepository
from app.schemas.prompts import PromptCapabilities, PromptCreate, PromptTemplate, PromptUpdate, VoiceConfig


class PromptRepository(JsonFileRepository):
    def __init__(self, data_file: Path | None = None) -> None:
        super().__init__("prompts.json", data_file=data_file)

    def list(self) -> list[PromptTemplate]:
        items = self._read_json()
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
            self._write_json(items)
        return [PromptTemplate(**item) for item in items]

    def create(self, payload: PromptCreate) -> PromptTemplate:
        with self._lock:
            items = self._read_json()
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
                "voice_config": payload.voice_config.model_dump(exclude_none=True)
                if isinstance(payload.voice_config, VoiceConfig)
                else payload.voice_config,
                "version": payload.version,
                "updated_at": now,
                "capabilities": capabilities,
            }
            items.append(record)
            self._write_json(items)
        return PromptTemplate(**record)

    def update(self, prompt_id: str, payload: PromptUpdate) -> PromptTemplate:
        with self._lock:
            items = self._read_json()
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
            self._write_json(items)
        return PromptTemplate(**target)

    def delete(self, prompt_id: str) -> None:
        with self._lock:
            items = self._read_json()
            filtered = [item for item in items if item["id"] != prompt_id]
            if len(filtered) == len(items):
                raise KeyError(prompt_id)
            self._write_json(filtered)


prompt_repository = PromptRepository()
