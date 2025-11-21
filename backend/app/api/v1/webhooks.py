from fastapi import APIRouter

from app.services.telephony import telephony_adapter

router = APIRouter()


@router.post("/telephony")
async def telephony_webhook(payload: dict):
    await telephony_adapter.handle_webhook(payload)
    return {"status": "received"}
