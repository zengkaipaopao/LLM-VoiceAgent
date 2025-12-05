from fastapi import APIRouter

from app.schemas.realtime import RealtimeSessionDTO, RealtimeSessionRequest
from app.services.realtime_service import realtime_service


router = APIRouter()


@router.post("/session", response_model=RealtimeSessionDTO, summary="Create OpenAI Realtime session")
async def create_realtime_session(payload: RealtimeSessionRequest) -> RealtimeSessionDTO:
    return await realtime_service.create_session(payload)
