from __future__ import annotations

from pathlib import Path

from app.repositories.base import JsonFileRepository
from app.schemas.appointments import AppointmentRecord


class AppointmentRepository(JsonFileRepository):
    def __init__(self, data_file: Path | None = None) -> None:
        super().__init__("appointments.json", data_file=data_file)

    def list(self) -> list[AppointmentRecord]:
        payload = self._read_json()
        return [AppointmentRecord(**item) for item in payload]

    def append(self, record: AppointmentRecord) -> AppointmentRecord:
        with self._lock:
            items = self._read_json()
            items.append(record.model_dump())
            self._write_json(items)
        return record


appointment_repository = AppointmentRepository()
