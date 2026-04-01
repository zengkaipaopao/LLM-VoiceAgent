"""
LLM related endpoints.
"""
import logging
from typing import List, Dict

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.schemas.base import ResponseBase
from app.services.llm.factory import LLMFactory

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/models", response_model=ResponseBase[Dict[str, List[str]]])
async def list_models(
    provider: str = Query(..., description="LLM provider name (gemini, openai, claude)")
):
    """
    List available models for a given provider.
    """
    try:
        # TODO: Get API key from settings based on provider
        api_key = ""
        if provider.lower() == "gemini":
            api_key = settings.google_api_key
        
        # Call factory to get models
        models = await LLMFactory.get_models(provider, api_key)
        
        return ResponseBase(success=True, data={"models": models})
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("Failed to list models for provider=%s", provider)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list models."
        ) from e
