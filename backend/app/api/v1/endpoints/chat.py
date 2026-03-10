"""
Chat API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.api.deps import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse
)
from app.schemas.base import ResponseBase
from app.services.chat_service import ChatService


router = APIRouter()

@router.post("", response_model=ResponseBase[ChatResponse], status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with LLM.
    
    Creates or updates a Call record and returns AI response.
    """
    try:
        service = ChatService(db)
        response_data = await service.process_chat(request)
        return ResponseBase(success=True, data=response_data)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Stream chat with LLM using Server-Sent Events.
    """
    try:
        service = ChatService(db)
        return StreamingResponse(
            service.stream_chat(request),
            media_type="text/event-stream"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        err_msg = str(e)
        # Return a simple error stream if initialized failure
        async def _error_stream():
            yield f"data: {json.dumps({'type': 'error', 'error': err_msg})}\n\n"
        return StreamingResponse(
            _error_stream(),
            media_type="text/event-stream"
        )


@router.post("/extract", response_model=ResponseBase[ExtractionResponse], status_code=status.HTTP_200_OK)
async def extract_appointment(
    request: ExtractionRequest,
    db: Session = Depends(get_db)
):
    """
    Extract appointment information from conversation.
    """
    try:
        service = ChatService(db)
        extraction_data = await service.extract_appointment(request)
        return ResponseBase(
            success=extraction_data.success,
            message=extraction_data.message,
            data=extraction_data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction error: {str(e)}"
        )
