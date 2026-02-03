"""
API v1 router.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import calls, call_simulation

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(calls.router)
api_router.include_router(call_simulation.router)  # 测试用模拟API

