"""
Chat API endpoints.
"""
import json
import logging

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
    TestSessionAppendMessagesRequest,
    TestSessionAppendMessagesResponse,
    TestSessionFinalizeRequest,
    TestSessionFinalizeResponse,
    TestSessionStartRequest,
    TestSessionStartResponse,
)
from app.services.chat_service import ChatService
from app.services.test_session_service import TestSessionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ResponseBase[ChatResponse], status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat with LLM."""
    try:
        service = ChatService(db)
        response_data = await service.process_chat(request)
        return ResponseBase(success=True, data=response_data)

    except ValueError as e:
        logger.warning("Invalid chat request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat request.",
        ) from e
    except Exception as e:
        logger.exception("Chat request failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat processing failed.",
        ) from e


@router.post("/test/start", response_model=ResponseBase[TestSessionStartResponse], status_code=status.HTTP_200_OK)
async def start_test_session(request: TestSessionStartRequest, db: AsyncSession = Depends(get_db)):
    """Start a unified test session with generated simulated phone number."""
    try:
        service = TestSessionService(db)
        result = await service.start_test_session(
            template_code=request.template_code,
            provider=request.provider,
            model=request.model,
            caller_name=request.caller_name,
            mode=request.mode,
        )
        return ResponseBase(success=True, data=result)
    except ValueError as e:
        logger.warning("Invalid test session start request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid test session request.",
        ) from e


@router.post(
    "/test/append-messages",
    response_model=ResponseBase[TestSessionAppendMessagesResponse],
    status_code=status.HTTP_200_OK,
)
async def append_test_session_messages(
    request: TestSessionAppendMessagesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Append normalized transcript messages to an existing test session."""
    try:
        service = TestSessionService(db)
        result = await service.append_test_session_messages(
            call_id=request.call_id,
            messages=request.messages,
            template_code=request.template_code,
            provider=request.provider,
            model=request.model,
        )
        return ResponseBase(success=True, data=result)
    except ValueError as e:
        logger.warning("Invalid append test session request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid append test session request.",
        ) from e
    except Exception as e:
        logger.exception("Failed to append test session messages.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to append test session messages.",
        ) from e
    except Exception as e:
        logger.exception("Failed to start test session.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start test session.",
        ) from e


@router.post(
    "/test/finalize",
    response_model=ResponseBase[TestSessionFinalizeResponse],
    status_code=status.HTTP_200_OK,
)
async def finalize_test_session(request: TestSessionFinalizeRequest, db: AsyncSession = Depends(get_db)):
    """Finalize test session and optionally extract appointment (idempotent)."""
    try:
        chat_service = ChatService(db)
        service = TestSessionService(
            db,
            call_repo=chat_service.call_repo,
            appointment_repo=chat_service.appointment_repo,
            prompt_service=chat_service.prompt_service,
            extract_appointment=chat_service.extract_appointment,
        )
        result = await service.finalize_test_session(
            call_id=request.call_id,
            template_code=request.template_code,
            run_extraction=request.run_extraction,
        )
        return ResponseBase(success=True, data=result)
    except ValueError as e:
        logger.warning("Invalid finalize session request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid finalize request.",
        ) from e
    except Exception as e:
        logger.exception("Failed to finalize test session.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize test session.",
        ) from e


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Stream chat with LLM using Server-Sent Events."""
    try:
        service = ChatService(db)
        return StreamingResponse(service.stream_chat(request), media_type="text/event-stream")
    except Exception:
        logger.exception("Failed to initialize chat stream.")
        err_msg = "Failed to initialize chat stream."

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
        logger.warning("Invalid extraction request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid extraction request.",
        ) from e
    except Exception as e:
        logger.exception("Appointment extraction request failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Appointment extraction failed.",
        ) from e
