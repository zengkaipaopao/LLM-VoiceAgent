from fastapi import APIRouter

from app.api.v1.endpoints import (
    appointment_simulation,
    appointments,
    call_simulation,
    calls,
    chat,
    dashboard,
    health,
    llm,
    prompts,
    realtime,
    twilio,
)

api_router = APIRouter()

# Existing routes
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(
    call_simulation.router,
    prefix="/calls/simulate",
    tags=["call-simulation"],
)
api_router.include_router(
    appointment_simulation.router,
    prefix="/appointments/simulate",
    tags=["appointment-simulation"],
)
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])

# New LLM chat routes
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(realtime.router, prefix="/live", tags=["live"])
