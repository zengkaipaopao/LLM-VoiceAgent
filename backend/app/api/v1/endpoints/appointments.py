from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from uuid import UUID
import math

from app.api.deps import get_db
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointments import AppointmentsResponse, AppointmentResponse

router = APIRouter()

@router.get("", response_model=AppointmentsResponse)
def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("timestamp"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    operation: Optional[str] = None,
    is_handled: Optional[bool] = None,
    type_name: Optional[str] = None,
    prompt_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """
    List appointments (read-only for simulation results).
    """
    repo = AppointmentRepository(db)
    items, total = repo.get_paginated(
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
        prompt_id=prompt_id
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return AppointmentsResponse(
        items=[AppointmentResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.patch("/{appointment_id}/handle", response_model=AppointmentResponse)
def handle_appointment(
    appointment_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark an appointment as handled.
    """
    repo = AppointmentRepository(db)
    appointment = repo.mark_as_handled(appointment_id, True)
    
    if not appointment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    return AppointmentResponse.model_validate(appointment)
