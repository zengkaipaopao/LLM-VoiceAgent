import math
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.appointments import AppointmentResponse, AppointmentsResponse
from app.schemas.base import PaginatedMetaWrapper, PaginationMeta, ResponseBase
from app.services.appointment_service import AppointmentService

router = APIRouter()


@router.get("", response_model=AppointmentsResponse)
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("timestamp"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    operation: Optional[str] = None,
    is_handled: Optional[bool] = None,
    type_name: Optional[str] = None,
    prompt_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentService(db)
    items, total = await service.get_paginated_appointments(
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

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return AppointmentsResponse(
        success=True,
        message="Success",
        data=[AppointmentResponse.model_validate(item) for item in items],
        meta=PaginatedMetaWrapper(
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total,
                total_pages=total_pages,
            )
        ),
    )


@router.patch("/{appointment_id}/handle", response_model=ResponseBase[AppointmentResponse])
async def handle_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentService(db)
    appointment = await service.handle_appointment(appointment_id)

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return ResponseBase(success=True, data=AppointmentResponse.model_validate(appointment))
