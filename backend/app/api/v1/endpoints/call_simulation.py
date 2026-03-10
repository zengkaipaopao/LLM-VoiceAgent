"""
Call simulation API endpoints for testing.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.services.call_simulation_service import CallSimulationService
from app.schemas.call import CallResponse
from app.schemas.base import ResponseBase

router = APIRouter()  # 移除prefix,在routes.py中统一管理



@router.post("/incoming", response_model=ResponseBase[CallResponse])
def simulate_incoming_call(
    scenario: str = Query(
        "ai_handled",
        description="Scenario type: ai_handled, transferred, no_answer, failed"
    ),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate an incoming call for testing.
    """
    service = CallSimulationService(db)
    call = service.simulate_incoming_call(scenario)
    
    return ResponseBase(success=True, data=CallResponse.model_validate(call))


@router.post("/batch", response_model=ResponseBase[List[CallResponse]])
def simulate_batch_calls(
    count: int = Query(10, ge=1, le=100, description="Number of calls to simulate"),
    enable_reviewer: bool = Query(True, description="Enable AI Reviewer (generate confidence score)"),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate multiple calls for testing.
    """
    service = CallSimulationService(db)
    calls = service.simulate_batch_calls(count, enable_reviewer)
    
    return ResponseBase(success=True, data=[CallResponse.model_validate(call) for call in calls])


@router.delete("/clear-test-data", response_model=ResponseBase[dict])
def clear_test_data(db: Session = Depends(get_db)):
    """
    🧹 Clear all simulated test calls.
    """
    from app.models.call import Call
    
    # Delete only simulated calls
    deleted = db.query(Call).filter(
        Call.extra_data['simulation'].astext == 'true'
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return ResponseBase(success=True, data={"deleted_count": deleted})
