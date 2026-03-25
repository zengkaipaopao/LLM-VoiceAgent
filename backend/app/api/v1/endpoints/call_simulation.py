"""
Call simulation API endpoints for testing.
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.call import Call
from app.schemas.base import ResponseBase
from app.schemas.call import CallResponse
from app.services.call_simulation_service import CallSimulationService

router = APIRouter()


@router.post("/incoming", response_model=ResponseBase[CallResponse])
async def simulate_incoming_call(
    scenario: str = Query("ai_handled", description="Scenario type: ai_handled, transferred, no_answer, failed"),
    db: AsyncSession = Depends(get_db),
):
    service = CallSimulationService(db)
    call = await service.simulate_incoming_call(scenario)
    return ResponseBase(success=True, data=CallResponse.model_validate(call))


@router.post("/batch", response_model=ResponseBase[List[CallResponse]])
async def simulate_batch_calls(
    count: int = Query(10, ge=1, le=100, description="Number of calls to simulate"),
    enable_reviewer: bool = Query(True, description="Enable AI Reviewer (generate confidence score)"),
    db: AsyncSession = Depends(get_db),
):
    service = CallSimulationService(db)
    calls = await service.simulate_batch_calls(count, enable_reviewer)
    return ResponseBase(success=True, data=[CallResponse.model_validate(call) for call in calls])


@router.delete("/clear-test-data", response_model=ResponseBase[dict])
async def clear_test_data(db: AsyncSession = Depends(get_db)):
    stmt = delete(Call).where(Call.extra_data["simulation"].astext == "true")
    result = await db.execute(stmt)
    await db.commit()
    return ResponseBase(success=True, data={"deleted_count": int(result.rowcount or 0)})
