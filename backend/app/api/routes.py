from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    appointments,
    call_simulation, 
    appointment_simulation,
    calls
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(call_simulation.router, prefix="/calls/simulate", tags=["call-simulation"])
api_router.include_router(appointment_simulation.router, prefix="/appointments/simulate", tags=["appointment-simulation"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
