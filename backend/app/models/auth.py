"""Administrative user identities."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    password_hash = Column(String(512), nullable=True)
    auth_provider = Column(String(32), nullable=False, default="local")
    external_subject = Column(String(255), nullable=True)
    role = Column(String(32), nullable=False, default="admin")
    is_active = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
