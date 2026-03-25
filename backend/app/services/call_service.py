"""
Call service for business logic.

This service handles call-related business logic.
It sits between the API layer and the Repository layer.

TODO: Implement real business logic when SIP service is ready.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call
from app.repositories.call_repository import CallRepository


class CallService:
    """Service for call business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CallRepository(db)

    async def list_calls(
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
        return await self.repo.get_paginated(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            order=order,
            status=status,
            handler_type=handler_type,
            start_date=start_date,
            end_date=end_date,
            search=search,
            filter_match=filter_match,
        )

    async def get_call_by_id(self, call_id: UUID) -> Optional[Call]:
        return await self.repo.get_by_id(call_id)

    async def get_recent_calls(self, limit: int = 10, status: Optional[str] = None) -> List[Call]:
        return await self.repo.get_recent(limit=limit, status=status)

    def create_outbound_call(self, counterpart: str, caller_name: Optional[str] = None, **kwargs) -> Call:
        raise NotImplementedError(
            "Outbound call creation requires SIP service integration. "
            "Currently only simulation is supported."
        )

    def answer_call(self, call_id: UUID) -> Call:
        raise NotImplementedError(
            "Call answering requires SIP service integration. "
            "Currently only simulation is supported."
        )

    def transfer_call(self, call_id: UUID, target: str, reason: Optional[str] = None) -> Call:
        raise NotImplementedError(
            "Call transfer requires SIP service integration. "
            "Currently only simulation is supported."
        )

    def end_call(self, call_id: UUID) -> Call:
        raise NotImplementedError(
            "Call ending requires SIP service integration. "
            "Currently only simulation is supported."
        )
