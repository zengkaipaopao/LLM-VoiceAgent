"""
API v1 router.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import calls, call_simulation, appointment_simulation, prompts, chat

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(calls.router)
api_router.include_router(call_simulation.router, prefix="/calls/simulate", tags=["Simulation"])  # 测试用模拟API
api_router.include_router(appointment_simulation.router, prefix="/appointments/simulate", tags=["Simulation"])

