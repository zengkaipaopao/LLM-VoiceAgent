from fastapi import APIRouter

from app.schemas.base import ResponseBase

router = APIRouter()


@router.get("/health", response_model=ResponseBase[dict])
async def health_check():
    return ResponseBase(success=True, data={"status": "ok"})
