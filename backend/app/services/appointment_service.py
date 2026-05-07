"""Read-model service for appointment management pages.

Realtime appointment creation, update, cancel, matching, and confirmation live
in the ``services.appointments`` domain package. This service intentionally
keeps list/detail helpers used by management APIs.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository


class AppointmentService:
    """Service for appointment business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AppointmentRepository(db)

    async def get_paginated_appointments(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        operation: Optional[str] = None,
        is_handled: Optional[bool] = None,
        type_name: Optional[str] = None,
        prompt_id: Optional[UUID] = None,
    ) -> Tuple[List[Appointment], int]:
        return await self.repo.get_paginated(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            order=order,
            start_date=start_date,
            end_date=end_date,
            search=search,
            operation=operation,
            is_handled=is_handled,
            type_name=type_name,
            prompt_id=prompt_id,
        )

    async def get_appointment_by_id(self, appointment_id: UUID) -> Optional[Appointment]:
        return await self.repo.get_by_id(appointment_id)

    async def get_appointment_by_call_id(self, call_id: UUID) -> Optional[Appointment]:
        return await self.repo.get_by_call_id(call_id)

    async def handle_appointment(self, appointment_id: str) -> Optional[Appointment]:
        return await self.repo.mark_as_handled(appointment_id, True)

    async def get_upcoming_appointments(self, limit: int = 10) -> List[Appointment]:
        return await self.repo.get_upcoming(limit=limit)

    def create_appointment(
        self,
        customer_phone: str,
        customer_name: str,
        appointment_time: datetime,
        service_type: str,
        **kwargs,
    ) -> Appointment:
        raise NotImplementedError(
            "Appointment creation is handled by the appointments domain services."
        )

    def update_appointment(self, appointment_id: UUID, **updates) -> Appointment:
        raise NotImplementedError(
            "Appointment updates are handled by the appointments domain services."
        )

    def confirm_appointment(self, appointment_id: UUID) -> Appointment:
        raise NotImplementedError(
            "Appointment confirmation is handled by the appointments domain services."
        )

    def cancel_appointment(self, appointment_id: UUID, reason: Optional[str] = None) -> Appointment:
        raise NotImplementedError(
            "Appointment cancellation is handled by the appointments domain services."
        )

    def reschedule_appointment(self, appointment_id: UUID, new_time: datetime) -> Appointment:
        raise NotImplementedError(
            "Appointment rescheduling is handled by the appointments domain services."
        )
