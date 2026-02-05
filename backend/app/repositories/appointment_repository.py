"""
Appointment repository for data access.
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from typing import List, Optional, Tuple
from datetime import datetime

from app.repositories.base_repository import BaseRepository
from app.models.appointment import Appointment

class AppointmentRepository(BaseRepository[Appointment]):
    """
    Repository for Appointment model.
    """
    
    def __init__(self, db: Session):
        super().__init__(Appointment, db)
    
    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Appointment], int]:
        """
        Get paginated appointments with filtering and sorting.
        """
        query = self.db.query(Appointment)
        
        # Apply filters
        if start_date:
            query = query.filter(Appointment.timestamp >= start_date)
        
        if end_date:
            query = query.filter(Appointment.timestamp <= end_date)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Appointment.caller_name.ilike(search_pattern),
                    Appointment.company.ilike(search_pattern),
                    Appointment.appointment.ilike(search_pattern)
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(Appointment, sort_by, Appointment.timestamp)
        if order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Apply pagination
        skip = (page - 1) * page_size
        items = query.offset(skip).limit(page_size).all()
        
        return items, total
