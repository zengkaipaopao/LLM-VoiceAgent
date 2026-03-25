"""
Appointment simulation API endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.appointments import AppointmentRecord
from app.schemas.base import ResponseBase
from app.services.appointment_simulation_service import AppointmentSimulationService

router = APIRouter()


@router.post("/incoming", response_model=ResponseBase[AppointmentRecord])
async def simulate_incoming_appointment(
    scenario: str = Query("new", description="Scenario type: new (新预约), update (预约变更), cancel (取消预约)"),
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentSimulationService(db)
    appt = await service.simulate_appointment(scenario)

    return ResponseBase(success=True, data=AppointmentRecord.model_validate(appt))


@router.post("/batch", response_model=ResponseBase[List[AppointmentRecord]])
async def simulate_batch_appointments(
    count: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentSimulationService(db)
    appts = await service.simulate_batch_appointments(count)

    return ResponseBase(success=True, data=[AppointmentRecord.model_validate(appt) for appt in appts])


@router.delete("/clear-test-data", response_model=ResponseBase[dict])
async def clear_test_data(db: AsyncSession = Depends(get_db)):
    service = AppointmentSimulationService(db)
    deleted = await service.clear_test_data()

    return ResponseBase(success=True, data={"deleted_count": deleted})
