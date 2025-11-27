from fastapi import APIRouter

from app.schemas.models import ModelInfo
from app.services.model_service import model_service

router = APIRouter()


@router.get("", response_model=list[ModelInfo])
async def list_models():
    """Expose available LLM models to the frontend."""
    return model_service.list_models()
