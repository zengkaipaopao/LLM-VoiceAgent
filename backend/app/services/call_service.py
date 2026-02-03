"""
Call service for business logic.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import math

from app.repositories.call_repository import CallRepository
from app.schemas.call import CallCreate, CallUpdate, CallResponse, CallListResponse
from app.exceptions import NotFoundException, BusinessException


class CallService:
    """
    Service for call business logic.
    
    Handles all business operations related to calls.
    """
    
    def __init__(self, db: Session):
        self.repo = CallRepository(db)
        self.db = db
    
    def create_call(self, call_data: CallCreate) -> CallResponse:
        """
        Create a new call record.
        
        Args:
            call_data: Call creation data
            
        Returns:
            Created call
            
        Raises:
            BusinessException: If validation fails
        """
        # Business logic: Set started_at if not provided
        data_dict = call_data.model_dump()
        if not data_dict.get('started_at'):
            data_dict['started_at'] = datetime.utcnow()
        
        # Create call
        call = self.repo.create(data_dict)
        return CallResponse.model_validate(call)
    
    def get_call(self, call_id: UUID) -> CallResponse:
        """
        Get a call by ID.
        
        Args:
            call_id: Call ID
            
        Returns:
            Call details
            
        Raises:
            NotFoundException: If call not found
        """
        call = self.repo.get(call_id)
        if not call:
            raise NotFoundException(f"Call {call_id} not found")
        
        return CallResponse.model_validate(call)
    
    def update_call(self, call_id: UUID, call_data: CallUpdate) -> CallResponse:
        """
        Update a call.
        
        Args:
            call_id: Call ID
            call_data: Update data
            
        Returns:
            Updated call
            
        Raises:
            NotFoundException: If call not found
        """
        call = self.repo.update(
            call_id, 
            call_data.model_dump(exclude_unset=True)
        )
        
        if not call:
            raise NotFoundException(f"Call {call_id} not found")
        
        return CallResponse.model_validate(call)
    
    def delete_call(self, call_id: UUID) -> bool:
        """
        Delete a call.
        
        Args:
            call_id: Call ID
            
        Returns:
            True if deleted
            
        Raises:
            NotFoundException: If call not found
        """
        deleted = self.repo.delete(call_id)
        if not deleted:
            raise NotFoundException(f"Call {call_id} not found")
        
        return True
    
    def list_calls(
        self, 
        page: int = 1, 
        page_size: int = 20,
        sort_by: str = "started_at",
        order: str = "desc",
        status: Optional[str] = None,
        handler_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> CallListResponse:
        """
        List calls with pagination, filtering, and sorting.
        
        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Field to sort by
            order: Sort order (asc/desc)
            status: Filter by status
            handler_type: Filter by handler type
            start_date: Filter by start date
            end_date: Filter by end date
            search: Search query
            
        Returns:
            Paginated call list
        """
        calls, total = self.repo.get_paginated(
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
            items=[CallResponse.model_validate(call) for call in calls],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    def get_recent_calls(self, limit: int = 10) -> List[CallResponse]:
        """
        Get recent calls.
        
        Args:
            limit: Maximum number of calls
            
        Returns:
            List of recent calls
        """
        calls = self.repo.get_recent(limit=limit)
        return [CallResponse.model_validate(call) for call in calls]
    
    def get_calls_by_phone(self, phone: str, limit: int = 10) -> List[CallResponse]:
        """
        Get calls by phone number.
        
        Args:
            phone: Phone number
            limit: Maximum number of calls
            
        Returns:
            List of calls
        """
        calls = self.repo.get_by_counterpart(phone, limit=limit)
        return [CallResponse.model_validate(call) for call in calls]
