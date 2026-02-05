"""
Appointment model for database.
"""
from sqlalchemy import Column, String, DateTime, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.models.base import Base, TimestampMixin

class Appointment(Base, TimestampMixin):
    """
    Appointment record model.
    """
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), index=True) # ForeignKey is optional strictly if we don't enforce constraints in app level often, but good to have. Schema has it.
    timestamp = Column(DateTime, nullable=False, index=True)
    caller_name = Column(String(100), nullable=False, index=True)
    company = Column(String(200))
    appointment = Column(DateTime, nullable=False)
    category = Column(String(50))
    amount = Column(String(100))
    address = Column(Text)
    summary = Column(Text)
    extra_request = Column(Text)
    raw_messages = Column(JSONB)
    operation = Column(String(10)) # create, update, delete

    def __repr__(self):
        return f"<Appointment {self.id} - {self.caller_name}>"
