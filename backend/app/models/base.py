"""
Base model for all SQLAlchemy models.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from app.core.database import Base


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps to models.
    """
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, nullable=False, default=datetime.utcnow)
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            nullable=False,
            default=datetime.utcnow,
            onupdate=datetime.utcnow
        )


__all__ = ["Base", "TimestampMixin"]
