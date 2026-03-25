"""
Call repository for data access.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallStatus
from app.repositories.base_repository import BaseRepository
from app.utils.datetime_utils import to_tokyo_naive


class CallRepository(BaseRepository[Call]):
    """Repository for Call model."""

    def __init__(self, db: AsyncSession):
        super().__init__(Call, db)

    async def get_by_counterpart(self, counterpart: str, limit: int = 10) -> List[Call]:
        stmt = (
            select(Call)
            .where(Call.counterpart == counterpart)
            .order_by(desc(Call.started_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 10, status: Optional[CallStatus] = None) -> List[Call]:
        stmt = select(Call)
        if status:
            stmt = stmt.where(Call.status == status)
        stmt = stmt.order_by(desc(Call.started_at)).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Call]:
        stmt = (
            select(Call)
            .where(Call.started_at >= start_date)
            .where(Call.started_at <= end_date)
            .order_by(desc(Call.started_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_ongoing_calls(self) -> List[Call]:
        stmt = select(Call).where(Call.status == CallStatus.ONGOING)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "started_at",
        order: str = "desc",
        status: Optional[str] = None,
        handler_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        filter_match: str = "and",
    ) -> Tuple[List[Call], int]:
        start_date = to_tokyo_naive(start_date)
        end_date = to_tokyo_naive(end_date)

        stmt = select(Call)

        filters = []
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            if len(statuses) > 1:
                filters.append(Call.status.in_(statuses))
            elif len(statuses) == 1:
                filters.append(Call.status == statuses[0])

        if handler_type:
            handler_types = [item.strip() for item in handler_type.split(",") if item.strip()]
            if len(handler_types) > 1:
                filters.append(Call.handler_type.in_(handler_types))
            elif len(handler_types) == 1:
                filters.append(Call.handler_type == handler_types[0])

        if filters:
            stmt = stmt.where(or_(*filters) if filter_match == "or" else and_(*filters))

        if start_date:
            stmt = stmt.where(Call.started_at >= start_date)
        if end_date:
            stmt = stmt.where(Call.started_at <= end_date)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Call.caller_name.ilike(search_pattern),
                    Call.counterpart.ilike(search_pattern),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar() or 0)

        sort_column = getattr(Call, sort_by, Call.started_at)
        stmt = stmt.order_by(asc(sort_column) if order == "asc" else desc(sort_column))

        skip = (page - 1) * page_size
        stmt = stmt.offset(skip).limit(page_size)
        items_result = await self.db.execute(stmt)
        calls = list(items_result.scalars().all())

        return calls, total
