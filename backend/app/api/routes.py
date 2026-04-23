from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.v1.endpoints import (
    appointment_simulation,
    appointments,
    call_simulation,
    calls,
    chat,
    dashboard,
    dialogflow,
    health,
    llm,
    prompts,
    realtime,
    twilio,
    twilio_incoming,
    twilio_legacy_stream,
    twilio_management,
    twilio_status,
    twilio_trace,
)

api_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_api_key)])

# Existing routes
api_router.include_router(health.router, tags=["health"])
protected_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
protected_router.include_router(
    call_simulation.router,
    prefix="/calls/simulate",
    tags=["call-simulation"],
)
protected_router.include_router(
    appointment_simulation.router,
    prefix="/appointments/simulate",
    tags=["appointment-simulation"],
)
protected_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
protected_router.include_router(calls.router, prefix="/calls", tags=["calls"])

# New LLM chat routes
protected_router.include_router(chat.router, prefix="/chat", tags=["chat"])
protected_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
protected_router.include_router(llm.router, prefix="/llm", tags=["llm"])
protected_router.include_router(realtime.router, prefix="/live", tags=["live"])
protected_router.include_router(dialogflow.router, prefix="/dialogflow", tags=["dialogflow"])

api_router.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(twilio_incoming.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(twilio_legacy_stream.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(twilio_management.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(twilio_status.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(twilio_trace.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(protected_router)
