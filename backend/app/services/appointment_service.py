from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException

from app.repositories.appointments import AppointmentRepository, appointment_repository
from app.schemas.appointments import AppointmentCreateRequest, AppointmentRecord


class AppointmentService:
    def __init__(self, repository: AppointmentRepository | None = None) -> None:
        self._repository = repository or appointment_repository

    def list_records(self) -> list[AppointmentRecord]:
        return self._repository.list()

    async def create_from_conversation(self, payload: AppointmentCreateRequest) -> AppointmentRecord:
        if not payload.summary.strip():
            raise HTTPException(status_code=400, detail="预约摘要不能为空")
        record = AppointmentRecord(id=str(uuid4()), **payload.model_dump())
        return self._repository.append(record)


appointment_service = AppointmentService()
