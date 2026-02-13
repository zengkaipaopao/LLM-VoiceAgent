"""
SQLAlchemy models package.
"""
from app.models.base import Base, TimestampMixin
from app.models.call import Call
from app.models.appointment import Appointment
from app.models.prompt_template import PromptTemplate

__all__ = ["Base", "TimestampMixin", "Call", "Appointment", "PromptTemplate"]
