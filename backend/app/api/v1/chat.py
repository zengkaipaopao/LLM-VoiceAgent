from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    return await chat_service.chat(payload)
