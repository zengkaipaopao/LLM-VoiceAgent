from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import math

from app.api.deps import get_db
from app.services.call_service import CallService
from app.schemas.call import CallListResponse, CallResponse

router = APIRouter()

@router.get("", response_model=CallListResponse)
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("started_at"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    status: Optional[str] = None,
    handler_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List calls (read-only for simulation results).
    
    Uses CallService layer for business logic.
    """
    # Use Service layer instead of direct Repository access
    service = CallService(db)
    items, total = service.list_calls(
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
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return CallListResponse(
        items=[CallResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
