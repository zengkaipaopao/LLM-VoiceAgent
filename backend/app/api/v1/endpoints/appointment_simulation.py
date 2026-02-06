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

@router.post("/incoming", response_model=AppointmentRecord)
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
    
    return AppointmentRecord.model_validate(appt)

@router.post("/batch", response_model=List[AppointmentRecord])
def simulate_batch_appointments(
    count: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate multiple appointments.
    """
    service = AppointmentSimulationService(db)
    appts = service.simulate_batch_appointments(count)
    
    return [AppointmentRecord.model_validate(appt) for appt in appts]

@router.delete("/clear-test-data", response_model=dict)
def clear_test_data(db: Session = Depends(get_db)):
    """
    🧹 Clear all simulated appointments.
    """
    service = AppointmentSimulationService(db)
    deleted = service.clear_test_data()
    
    return {"deleted_count": deleted, "success": True}
