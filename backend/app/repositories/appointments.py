from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.schemas.appointments import AppointmentRecord


class AppointmentRepository:
    def __init__(self, data_file: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._data_file = data_file or base_dir / "data" / "appointments.json"
        self._lock = Lock()
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            self._data_file.write_text("[]", encoding="utf-8")

    def _read_file(self) -> list[dict[str, Any]]:
        if not self._data_file.exists():
            return []
        raw = self._data_file.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        return json.loads(raw)

    def list(self) -> list[AppointmentRecord]:
        payload = self._read_file()
        return [AppointmentRecord(**item) for item in payload]

    def append(self, record: AppointmentRecord) -> AppointmentRecord:
        with self._lock:
            items = self._read_file()
            items.append(record.model_dump())
            self._data_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return record


appointment_repository = AppointmentRepository()
