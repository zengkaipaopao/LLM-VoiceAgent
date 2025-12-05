from fastapi import APIRouter

from app.schemas.appointments import AppointmentCreateRequest, AppointmentRecord
from app.services.appointment_service import appointment_service

router = APIRouter()


@router.get("", response_model=list[AppointmentRecord])
async def list_appointments() -> list[AppointmentRecord]:
    return appointment_service.list_records()


@router.post("", response_model=AppointmentRecord, summary="从会话日志生成预约记录")
async def create_appointment(payload: AppointmentCreateRequest) -> AppointmentRecord:
    return await appointment_service.create_from_conversation(payload)
