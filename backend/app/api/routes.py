from fastapi import APIRouter

from app.api.v1 import (
    appointments,
    chat,
    health,
    models,
    prompts,
    realtime,
    tts,
    twilio_voice,
    webhooks,
)
from app.api.v1.endpoints import call_simulation, calls  # 从endpoints子目录导入

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(calls.router, tags=["calls"])  # 移除prefix,在calls.py中已定义
api_router.include_router(call_simulation.router, prefix="/calls/simulate", tags=["call-simulation"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(twilio_voice.router, prefix="/twilio", tags=["twilio"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

