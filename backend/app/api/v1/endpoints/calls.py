"""
Call API endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from app.api.deps import get_db
from app.services.call_service import CallService
from app.schemas.call import CallCreate, CallUpdate, CallResponse, CallListResponse
from app.schemas.base import ResponseBase

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("", response_model=ResponseBase[CallResponse], status_code=201)
def create_call(
    *,
    db: Session = Depends(get_db),
    call_in: CallCreate
):
    """
    Create a new call record.
    
    - **direction**: Call direction (inbound/outbound)
    - **counterpart**: Phone number of the other party
    - **prompt_id**: Optional prompt ID to use
    """
    service = CallService(db)
    call = service.create_call(call_in)
    return ResponseBase(
        success=True,
        message="Call created successfully",
        data=call
    )


@router.get("/{call_id}", response_model=ResponseBase[CallResponse])
def get_call(
    call_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a call by ID.
    """
    service = CallService(db)
    call = service.get_call(call_id)
    return ResponseBase(
        success=True,
        message="Call retrieved successfully",
        data=call
    )


@router.put("/{call_id}", response_model=ResponseBase[CallResponse])
def update_call(
    call_id: UUID,
    call_in: CallUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a call.
    
    - **status**: Update call status
    - **summary**: Add call summary
    - **transcript**: Add call transcript
    - **duration_seconds**: Update call duration
    """
    service = CallService(db)
    call = service.update_call(call_id, call_in)
    return ResponseBase(
        success=True,
        message="Call updated successfully",
        data=call
    )


@router.delete("/{call_id}", response_model=ResponseBase[bool])
def delete_call(
    call_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete a call.
    """
    service = CallService(db)
    service.delete_call(call_id)
    return ResponseBase(
        success=True,
        message="Call deleted successfully",
        data=True
    )


@router.get("", response_model=ResponseBase[CallListResponse])
def list_calls(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("started_at", description="Field to sort by"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    status: Optional[str] = Query(None, description="Filter by status"),
    handler_type: Optional[str] = Query(None, description="Filter by handler type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (>=)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (<=)"),
    search: Optional[str] = Query(None, description="Search in caller name or phone number"),
    db: Session = Depends(get_db)
):
    """
    List calls with pagination, filtering, and sorting.
    
    **Pagination**:
    - `page`: Page number (starts from 1)
    - `page_size`: Number of items per page (max 100)
    
    **Sorting**:
    - `sort_by`: Field to sort by (e.g., started_at, duration_seconds, ai_confidence)
    - `order`: Sort order (asc or desc)
    
    **Filtering**:
    - `status`: Filter by call status
    - `handler_type`: Filter by handler type (ai/human/transferred)
    - `start_date`: Filter calls starting from this date
    - `end_date`: Filter calls up to this date
    - `search`: Search in caller name or phone number
    """
    service = CallService(db)
    result = service.list_calls(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
        status=status,
        handler_type=handler_type,
        start_date=start_date,
        end_date=end_date,
        search=search
    )
    return ResponseBase(
        success=True,
        message="Calls retrieved successfully",
        data=result
    )


@router.get("/recent/list", response_model=ResponseBase[List[CallResponse]])
def get_recent_calls(
    limit: int = Query(10, ge=1, le=50, description="Number of calls to return"),
    db: Session = Depends(get_db)
):
    """
    Get recent calls.
    
    - **limit**: Number of recent calls to return (max 50)
    """
    service = CallService(db)
    calls = service.get_recent_calls(limit=limit)
    return ResponseBase(
        success=True,
        message="Recent calls retrieved successfully",
        data=calls
    )


@router.get("/phone/{phone}", response_model=ResponseBase[List[CallResponse]])
def get_calls_by_phone(
    phone: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get calls by phone number.
    
    - **phone**: Phone number to search for
    - **limit**: Maximum number of calls to return
    """
    service = CallService(db)
    calls = service.get_calls_by_phone(phone, limit=limit)
    return ResponseBase(
        success=True,
        message=f"Calls for {phone} retrieved successfully",
        data=calls
    )
