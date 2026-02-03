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
    
    **Scenarios**:
    - `ai_handled`: AI successfully handles the call (60% probability)
    - `transferred`: AI transfers to human agent (25% probability)
    - `no_answer`: Customer doesn't answer (10% probability)
    - `failed`: Call fails (5% probability)
    
    **Use Case**:
    - Testing the call flow without real SIP connection
    - In production, replace this with actual SIP event handlers
    
    **Example**:
    ```
    POST /api/v1/calls/simulate/incoming?scenario=transferred
    ```
    """
    service = CallSimulationService(db)
    call = service.simulate_incoming_call(scenario)
    
    return ResponseBase(
        success=True,
        message=f"Simulated {scenario} call successfully",
        data=CallResponse.model_validate(call)
    )


@router.post("/batch", response_model=ResponseBase[List[CallResponse]])
def simulate_batch_calls(
    count: int = Query(10, ge=1, le=100, description="Number of calls to simulate"),
    db: Session = Depends(get_db)
):
    """
    🧪 Simulate multiple calls for testing.
    
    Creates multiple calls with realistic distribution:
    - 60% AI handled
    - 25% Transferred to human
    - 10% No answer
    - 5% Failed
    
    **Use Case**:
    - Populate database with test data
    - Test pagination and filtering
    - Performance testing
    
    **Example**:
    ```
    POST /api/v1/calls/simulate/batch?count=50
    ```
    """
    service = CallSimulationService(db)
    calls = service.simulate_batch_calls(count)
    
    return ResponseBase(
        success=True,
        message=f"Simulated {count} calls successfully",
        data=[CallResponse.model_validate(call) for call in calls]
    )


@router.delete("/clear-test-data", response_model=ResponseBase[dict])
def clear_test_data(db: Session = Depends(get_db)):
    """
    🧹 Clear all simulated test calls.
    
    Deletes all calls where extra_data.simulation = true.
    
    **Warning**: This only deletes test data, not real calls.
    """
    from app.models.call import Call
    
    # Delete only simulated calls
    deleted = db.query(Call).filter(
        Call.extra_data['simulation'].astext == 'true'
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return ResponseBase(
        success=True,
        message=f"Cleared {deleted} test calls",
        data={"deleted_count": deleted}
    )
