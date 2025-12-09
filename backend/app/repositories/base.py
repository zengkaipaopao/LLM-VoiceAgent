from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class JsonFileRepository:
    """Shared helpers for simple JSON-file repositories."""

    def __init__(
        self,
        filename: str,
        *,
        data_file: Path | None = None,
        default_payload: Any | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._data_file = data_file or base_dir / "data" / filename
        self._lock = Lock()
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            initial = default_payload if default_payload is not None else []
            self._write_json(initial)

    def _read_json(self) -> Any:
        if not self._data_file.exists():
            return []
        raw = self._data_file.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)

    def _write_json(self, payload: Any) -> None:
        self._data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
