from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.models import ModelInfo
from app.services.model_service import model_service

router = APIRouter()


class AllowedModelsPayload(BaseModel):
    ids: list[str]


@router.get("", response_model=list[ModelInfo])
async def list_models():
    """Expose available LLM models to the frontend."""
    try:
        return model_service.list_models()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/allowed", response_model=list[str])
async def list_allowed_models():
    return model_service.list_allowed_model_ids()


@router.put("/allowed", response_model=list[str])
async def update_allowed_models(payload: AllowedModelsPayload):
    try:
        return model_service.update_allowed_models(payload.ids)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="更新模型白名单失败") from exc
