from datetime import datetime
from typing import Optional

import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.base import PaginatedMetaWrapper, PaginationMeta
from app.schemas.call import CallListResponse, CallResponse
from app.services.call_service import CallService

router = APIRouter()


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("started_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    status: Optional[str] = None,
    handler_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    filter_match: str = Query("and", pattern="^(and|or)$"),
    db: AsyncSession = Depends(get_db),
):
    service = CallService(db)
    items, total = await service.list_calls(
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

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return CallListResponse(
        success=True,
        message="Success",
        data=[CallResponse.model_validate(item) for item in items],
        meta=PaginatedMetaWrapper(
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
            )
        ),
    )
