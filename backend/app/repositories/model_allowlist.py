from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class ModelAllowlistRepository:
    def __init__(self, data_file: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._data_file = data_file or base_dir / "data" / "model_allowlist.json"
        self._lock = Lock()
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            self._write([])

    def _read(self) -> list[str]:
        raw = self._data_file.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)

    def _write(self, payload: list[str]) -> None:
        self._data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[str]:
        return self._read()

    def set(self, model_ids: list[str]) -> list[str]:
        unique = sorted({model_id.strip() for model_id in model_ids if model_id.strip()})
        with self._lock:
            self._write(unique)
        return unique


model_allowlist_repository = ModelAllowlistRepository()
