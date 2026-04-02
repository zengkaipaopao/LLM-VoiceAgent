"""
Appointment repository for data access.
"""
from datetime import date, datetime, time
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.base_repository import BaseRepository
from app.utils.datetime_utils import now_tokyo_naive, to_tokyo_naive


class AppointmentRepository(BaseRepository[Appointment]):
    """Repository for Appointment model."""

    def __init__(self, db: AsyncSession):
        super().__init__(Appointment, db)

    async def get_paginated(
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
        start_date = to_tokyo_naive(start_date)
        end_date = to_tokyo_naive(end_date)

        stmt = select(Appointment)

        if operation:
            ops = [op.strip() for op in operation.split(",") if op.strip()]
            if ops:
                stmt = stmt.where(Appointment.operation.in_(ops))

        if is_handled is not None:
            stmt = stmt.where(Appointment.is_handled == is_handled)

        if type_name:
            stmt = stmt.where(Appointment.type_name == type_name)

        if prompt_id:
            stmt = stmt.where(Appointment.prompt_id == prompt_id)

        if start_date:
            stmt = stmt.where(Appointment.timestamp >= start_date)

        if end_date:
            stmt = stmt.where(Appointment.timestamp <= end_date)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Appointment.caller_name.ilike(search_pattern),
                    Appointment.company.ilike(search_pattern),
                    cast(Appointment.appointment, String).ilike(search_pattern),
                    Appointment.category.ilike(search_pattern),
                    Appointment.summary.ilike(search_pattern),
                    Appointment.extra_request.ilike(search_pattern),
                    Appointment.address.ilike(search_pattern),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar() or 0)

        sort_column = getattr(Appointment, sort_by, Appointment.timestamp)
        stmt = stmt.order_by(asc(sort_column) if order == "asc" else desc(sort_column))

        skip = (page - 1) * page_size
        stmt = stmt.offset(skip).limit(page_size)
        items_result = await self.db.execute(stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def get_by_call_id(self, call_id: UUID) -> Optional[Appointment]:
        """Get most recent appointment linked to a call."""
        stmt = (
            select(Appointment)
            .where(Appointment.call_id == call_id)
            .order_by(desc(Appointment.created_at))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_as_handled(self, appointment_id: str, is_handled: bool = True) -> Optional[Appointment]:
        appointment = await self.get(appointment_id)
        if appointment:
            appointment.is_handled = is_handled
            await self.db.commit()
            await self.db.refresh(appointment)
        return appointment

    async def get_upcoming(self, limit: int = 10) -> List[Appointment]:
        now = now_tokyo_naive()
        stmt = (
            select(Appointment)
            .where(Appointment.appointment >= now)
            .order_by(asc(Appointment.appointment))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_operation_candidates(
        self,
        *,
        caller_name: Optional[str] = None,
        counterpart: Optional[str] = None,
        appointment_date: Optional[date] = None,
        limit: int = 5,
    ) -> List[Appointment]:
        """Search existing appointments for update/cancel operations."""
        stmt = (
            select(Appointment)
            .join(Call, Appointment.call_id == Call.id, isouter=True)
            .where(or_(Appointment.operation == "create", Appointment.operation.is_(None)))
        )
        filters = []

        if caller_name:
            caller_pattern = f"%{caller_name.strip()}%"
            filters.append(
                or_(
                    Appointment.caller_name.ilike(caller_pattern),
                    Call.caller_name.ilike(caller_pattern),
                )
            )

        if counterpart:
            normalized = counterpart.strip()
            if normalized:
                filters.append(Call.counterpart == normalized)

        if appointment_date:
            start_dt = datetime.combine(appointment_date, time.min)
            end_dt = datetime.combine(appointment_date, time.max)
            filters.append(Appointment.appointment >= start_dt)
            filters.append(Appointment.appointment <= end_dt)

        # Never fall back to a full-table scan for operation candidates.
        # Update/cancel flows must be based on at least one identifying signal.
        if not filters:
            return []

        for condition in filters:
            stmt = stmt.where(condition)

        stmt = stmt.order_by(desc(Appointment.timestamp)).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_operation_candidates_with_call(
        self,
        *,
        caller_name: Optional[str] = None,
        company: Optional[str] = None,
        counterpart: Optional[str] = None,
        appointment_date: Optional[date] = None,
        limit: int = 30,
    ) -> List[Tuple[Appointment, Optional[Call]]]:
        """Search candidate appointments by any identifying hint for operation matching."""
        stmt = (
            select(Appointment, Call)
            .join(Call, Appointment.call_id == Call.id, isouter=True)
            .where(or_(Appointment.operation == "create", Appointment.operation.is_(None)))
        )
        any_filters = []

        if caller_name:
            caller_pattern = f"%{caller_name.strip()}%"
            any_filters.append(
                or_(
                    Appointment.caller_name.ilike(caller_pattern),
                    Call.caller_name.ilike(caller_pattern),
                )
            )

        if company:
            company_pattern = f"%{company.strip()}%"
            any_filters.append(Appointment.company.ilike(company_pattern))

        if counterpart:
            normalized = counterpart.strip()
            if normalized:
                any_filters.append(Call.counterpart == normalized)

        if appointment_date:
            start_dt = datetime.combine(appointment_date, time.min)
            end_dt = datetime.combine(appointment_date, time.max)
            any_filters.append(Appointment.appointment.between(start_dt, end_dt))

        if not any_filters:
            return []

        stmt = stmt.where(or_(*any_filters)).order_by(desc(Appointment.timestamp)).limit(limit)
        result = await self.db.execute(stmt)
        rows = []
        for appointment, related_call in result.all():
            rows.append((appointment, related_call))
        return rows
