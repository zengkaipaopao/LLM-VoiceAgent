from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.appointments import AppointmentCreateRequest, AppointmentRecord
from app.services.appointment_service import appointment_service

router = APIRouter()


@router.get("")
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "timestamp",
    order: str = "desc",
    search: Optional[str] = None,
    start_date: Optional[str] = None,

    end_date: Optional[str] = None,
    operation: Optional[str] = None,
    is_handled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Get paginated appointments.
    """
    return appointment_service.list_records_paginated(
        db, 
        page=page, 
        page_size=page_size, 
        sort_by=sort_by, 
        order=order,
        search=search,
        start_date=start_date,
        end_date=end_date,
        operation=operation,
        is_handled=is_handled
    )


@router.post("", response_model=AppointmentRecord, summary="从会话日志生成预约记录")
async def create_appointment(
    payload: AppointmentCreateRequest,
    db: Session = Depends(get_db)
) -> AppointmentRecord:
    return await appointment_service.create_from_conversation(payload, db)


@router.patch("/{appointment_id}/handle", response_model=AppointmentRecord, summary="标记预约为已对应")
async def handle_appointment(
    appointment_id: str,
    db: Session = Depends(get_db)
) -> AppointmentRecord:
    """
    标记预约为已处理（对应完毕）
    """
    return await appointment_service.mark_as_handled(appointment_id, db)
