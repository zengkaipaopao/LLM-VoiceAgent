"""
LLM related endpoints.
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Dict

from app.core.config import settings
from app.services.llm.factory import LLMFactory

router = APIRouter()

@router.get("/models", response_model=Dict[str, List[str]])
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
        
        return {"models": models}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )
