"""
Appointment simulation API endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.services.appointment_simulation_service import AppointmentSimulationService
from app.schemas.appointments import AppointmentRecord
from app.schemas.base import ResponseBase

router = APIRouter()

@router.post("/incoming", response_model=ResponseBase[AppointmentRecord])
def simulate_incoming_appointment(
    scenario: str = Query(
        "new",
        description="Scenario type: new (新预约), update (预约变更), cancel (取消预约)"
    ),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate an incoming appointment.
    """
    service = AppointmentSimulationService(db)
    appt = service.simulate_appointment(scenario)
    
    return ResponseBase(
        success=True,
        message=f"Simulated {scenario} appointment successfully",
        data=appt # Pydantic v2 automatic conversion if config allows, else manual maybe needed
    )

@router.post("/batch", response_model=ResponseBase[List[AppointmentRecord]])
def simulate_batch_appointments(
    count: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate multiple appointments.
    """
    service = AppointmentSimulationService(db)
    appts = service.simulate_batch_appointments(count)
    
    return ResponseBase(
        success=True,
        message=f"Simulated {count} appointments successfully",
        data=appts
    )

@router.delete("/clear-test-data", response_model=ResponseBase[dict])
def clear_test_data(db: Session = Depends(get_db)):
    """
    🧹 Clear all simulated appointments.
    """
    service = AppointmentSimulationService(db)
    deleted = service.clear_test_data()
    
    return ResponseBase(
        success=True,
        message=f"Cleared {deleted} test appointments",
        data={"deleted_count": deleted}
    )
