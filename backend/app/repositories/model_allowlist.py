from __future__ import annotations

from pathlib import Path

from app.repositories.base import JsonFileRepository


class ModelAllowlistRepository(JsonFileRepository):
    def __init__(self, data_file: Path | None = None) -> None:
        super().__init__("model_allowlist.json", data_file=data_file)

    def list(self) -> list[str]:
        return self._read_json()

    def set(self, model_ids: list[str]) -> list[str]:
        unique = sorted({model_id.strip() for model_id in model_ids if model_id.strip()})
        with self._lock:
            self._write_json(unique)
        return unique


model_allowlist_repository = ModelAllowlistRepository()
