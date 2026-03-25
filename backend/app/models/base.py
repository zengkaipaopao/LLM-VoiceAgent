"""
Base model for all SQLAlchemy models.
"""
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from app.core.database import Base
from app.utils.datetime_utils import now_tokyo_naive


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps to models.
    """
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, nullable=False, default=now_tokyo_naive)
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            nullable=False,
            default=now_tokyo_naive,
            onupdate=now_tokyo_naive
        )


__all__ = ["Base", "TimestampMixin"]
