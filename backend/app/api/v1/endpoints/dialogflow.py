from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.base import ResponseBase
from app.schemas.dialogflow import (
    DialogflowCreateAppointmentToolRequest,
    DialogflowCreateAppointmentToolResponse,
)
from app.services.dialogflow_tool_service import DialogflowToolService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/appointments/create",
    response_model=ResponseBase[DialogflowCreateAppointmentToolResponse],
    status_code=status.HTTP_200_OK,
)
async def create_appointment_from_playbook(
    request: DialogflowCreateAppointmentToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Persist a new appointment from a Conversational Agents playbook tool call."""
    try:
        service = DialogflowToolService(db)
        result = await service.create_new_appointment(request)
        return ResponseBase(success=True, data=result, message=result.message)
    except ValueError as exc:
        logger.warning("Invalid Dialogflow playbook appointment request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to create appointment from playbook tool.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create appointment from playbook tool.",
        ) from exc
