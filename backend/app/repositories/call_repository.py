"""
Call repository for data access.
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_, func
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from app.repositories.base_repository import BaseRepository
from app.models.call import Call, CallStatus


class CallRepository(BaseRepository[Call]):
    """
    Repository for Call model.
    
    Provides data access methods for call records.
    """
    
    def __init__(self, db: Session):
        super().__init__(Call, db)
    
    def get_by_counterpart(self, counterpart: str, limit: int = 10) -> List[Call]:
        """
        Get calls by phone number.
        
        Args:
            counterpart: Phone number
            limit: Maximum number of results
            
        Returns:
            List of calls
        """
        return self.db.query(Call)\
            .filter(Call.counterpart == counterpart)\
            .order_by(desc(Call.started_at))\
            .limit(limit)\
            .all()
    
    def get_recent(self, limit: int = 10, status: Optional[CallStatus] = None) -> List[Call]:
        """
        Get recent calls.
        
        Args:
            limit: Maximum number of results
            status: Optional status filter
            
        Returns:
            List of recent calls
        """
        query = self.db.query(Call)
        
        if status:
            query = query.filter(Call.status == status)
        
        return query.order_by(desc(Call.started_at)).limit(limit).all()
    
    def get_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Call]:
        """
        Get calls within date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of calls
        """
        return self.db.query(Call)\
            .filter(Call.started_at >= start_date)\
            .filter(Call.started_at <= end_date)\
            .order_by(desc(Call.started_at))\
            .all()
    
    def get_ongoing_calls(self) -> List[Call]:
        """
        Get all ongoing calls.
        
        Returns:
            List of ongoing calls
        """
        return self.db.query(Call)\
            .filter(Call.status == CallStatus.ONGOING)\
            .all()
    
    def get_paginated(
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
    ) -> Tuple[List[Call], int]:
        """
        Get paginated calls with filtering and sorting.
        
        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Field to sort by
            order: Sort order (asc/desc)
            status: Filter by status
            handler_type: Filter by handler type
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            search: Search in caller_name or counterpart
            
        Returns:
            Tuple of (calls list, total count)
        """
        query = self.db.query(Call)
        
        # Apply filters
        if status:
            query = query.filter(Call.status == status)
        
        if handler_type:
            query = query.filter(Call.handler_type == handler_type)
        
        if start_date:
            query = query.filter(Call.started_at >= start_date)
        
        if end_date:
            query = query.filter(Call.started_at <= end_date)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Call.caller_name.ilike(search_pattern),
                    Call.counterpart.ilike(search_pattern)
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(Call, sort_by, Call.started_at)
        if order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Apply pagination
        skip = (page - 1) * page_size
        calls = query.offset(skip).limit(page_size).all()
        
        return calls, total
