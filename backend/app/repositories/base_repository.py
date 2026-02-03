"""
Base Repository for data access layer.

Provides generic CRUD operations for all repositories.
"""
from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations.
    
    Type Parameters:
        ModelType: SQLAlchemy model type
        
    Example:
        class CallRepository(BaseRepository[Call]):
            def __init__(self, db: Session):
                super().__init__(Call, db)
    """
    
    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize repository.
        
        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db
    
    def get(self, id: Any) -> Optional[ModelType]:
        """
        Get a single record by ID.
        
        Args:
            id: Record ID
            
        Returns:
            Model instance or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Get multiple records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters as dict
            
        Returns:
            List of model instances
        """
        query = self.db.query(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records.
        
        Args:
            filters: Optional filters as dict
            
        Returns:
            Number of records
        """
        query = self.db.query(func.count(self.model.id))
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.scalar()
    
    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a new record.
        
        Args:
            obj_in: Data to create record from
            
        Returns:
            Created model instance
        """
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(
        self, 
        id: Any, 
        obj_in: Dict[str, Any]
    ) -> Optional[ModelType]:
        """
        Update a record.
        
        Args:
            id: Record ID
            obj_in: Data to update
            
        Returns:
            Updated model instance or None if not found
        """
        db_obj = self.get(id)
        if not db_obj:
            return None
        
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: Any) -> bool:
        """
        Delete a record.
        
        Args:
            id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        db_obj = self.get(id)
        if not db_obj:
            return False
        
        self.db.delete(db_obj)
        self.db.commit()
        return True
    
    def exists(self, id: Any) -> bool:
        """
        Check if a record exists.
        
        Args:
            id: Record ID
            
        Returns:
            True if exists, False otherwise
        """
        return self.db.query(
            self.db.query(self.model).filter(self.model.id == id).exists()
        ).scalar()
