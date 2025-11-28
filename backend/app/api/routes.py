from fastapi import APIRouter

from app.api.v1 import calls, chat, health, models, prompts, webhooks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
