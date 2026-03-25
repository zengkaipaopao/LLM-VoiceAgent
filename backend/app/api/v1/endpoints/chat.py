"""
Chat API endpoints.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.base import ResponseBase
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse,
    TestSessionFinalizeRequest,
    TestSessionFinalizeResponse,
    TestSessionStartRequest,
    TestSessionStartResponse,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("", response_model=ResponseBase[ChatResponse], status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat with LLM."""
    try:
        service = ChatService(db)
        response_data = await service.process_chat(request)
        return ResponseBase(success=True, data=response_data)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Chat error: {str(e)}")


@router.post("/test/start", response_model=ResponseBase[TestSessionStartResponse], status_code=status.HTTP_200_OK)
async def start_test_session(request: TestSessionStartRequest, db: AsyncSession = Depends(get_db)):
    """Start a unified test session with generated simulated phone number."""
    try:
        service = ChatService(db)
        result = await service.start_test_session(
            template_code=request.template_code,
            provider=request.provider,
            model=request.model,
            caller_name=request.caller_name,
        )
        return ResponseBase(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Start test session error: {str(e)}",
        )


@router.post(
    "/test/finalize",
    response_model=ResponseBase[TestSessionFinalizeResponse],
    status_code=status.HTTP_200_OK,
)
async def finalize_test_session(request: TestSessionFinalizeRequest, db: AsyncSession = Depends(get_db)):
    """Finalize test session and optionally extract appointment (idempotent)."""
    try:
        service = ChatService(db)
        result = await service.finalize_test_session(
            call_id=request.call_id,
            template_code=request.template_code,
            run_extraction=request.run_extraction,
        )
        return ResponseBase(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Finalize test session error: {str(e)}",
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Stream chat with LLM using Server-Sent Events."""
    try:
        service = ChatService(db)
        return StreamingResponse(service.stream_chat(request), media_type="text/event-stream")
    except Exception as e:
        err_msg = str(e)

        async def _error_stream():
            yield f"data: {json.dumps({'type': 'error', 'error': err_msg})}\n\n"

        return StreamingResponse(_error_stream(), media_type="text/event-stream")


@router.post("/extract", response_model=ResponseBase[ExtractionResponse], status_code=status.HTTP_200_OK)
async def extract_appointment(request: ExtractionRequest, db: AsyncSession = Depends(get_db)):
    """Extract appointment information from conversation."""
    try:
        service = ChatService(db)
        extraction_data = await service.extract_appointment(request)
        return ResponseBase(
            success=extraction_data.success,
            message=extraction_data.message,
            data=extraction_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction error: {str(e)}",
        )
