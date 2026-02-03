"""
Call model for database.
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
import enum

from app.models.base import Base, TimestampMixin


class CallDirection(str, enum.Enum):
    """Call direction enum."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    """Call status enum."""
    RINGING = "ringing"          # 响铃中
    ONGOING = "ongoing"          # 进行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    NO_ANSWER = "no_answer"      # 未接听
    BUSY = "busy"                # 忙线


class HandlerType(str, enum.Enum):
    """Handler type enum."""
    AI = "ai"                    # AI处理
    HUMAN = "human"              # 人工处理
    TRANSFERRED = "transferred"  # 已转接


class Call(Base, TimestampMixin):
    """
    Call record model.
    
    Attributes:
        # 基础信息
        id: Unique identifier
        direction: Call direction (inbound/outbound)
        counterpart: Phone number of the other party
        caller_name: Caller name (if available)
        
        # 时间信息
        started_at: When the call started
        answered_at: When the call was answered
        ended_at: When the call ended
        duration_seconds: Call duration in seconds
        
        # 状态信息
        status: Current call status
        handler_type: Who handled the call (AI/Human)
        is_answered: Whether the call was answered
        
        # 内容信息
        summary: Call summary
        transcript: Call transcript
        ai_confidence: AI confidence score (0-1)
        
        # 转接信息
        transferred_at: When transferred to human
        transfer_reason: Why transferred
        
        # SIP信息
        sip_call_id: SIP session ID
        sip_from: SIP From header
        sip_to: SIP To header
        
        # 关联信息
        prompt_id: Associated prompt ID
        agent_id: Associated agent ID
        
        # 元数据 (JSON格式,存储额外信息)
    # 注意: 'metadata' 是 SQLAlchemy 保留字,使用 'extra_data' 代替
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    """
    
    __tablename__ = "calls"
    
    # 基础信息
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction = Column(String(20), nullable=False)  # 使用String而不是Enum
    counterpart = Column(String(50), nullable=False, index=True)
    caller_name = Column(String(100))
    
    # 时间信息
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    answered_at = Column(DateTime)
    ended_at = Column(DateTime)
    duration_seconds = Column(Integer, default=0)
    
    # 状态信息
    status = Column(String(20), nullable=False, default=CallStatus.RINGING.value, index=True)  # 使用String
    handler_type = Column(String(20), default=HandlerType.AI.value, index=True)  # 使用String
    is_answered = Column(Boolean, default=False)

    
    # 内容信息
    summary = Column(Text)
    transcript = Column(Text)
    ai_confidence = Column(Integer)  # 0-100
    
    # 转接信息
    transferred_at = Column(DateTime)
    transfer_reason = Column(String(200))
    
    # SIP信息
    sip_call_id = Column(String(100), index=True)
    sip_from = Column(String(100))
    sip_to = Column(String(100))
    
    # 关联信息
    prompt_id = Column(UUID(as_uuid=True), index=True)
    agent_id = Column(UUID(as_uuid=True))
    
    # 元数据 (JSON格式,存储额外信息)
    # 注意: 'metadata' 是 SQLAlchemy 保留字,使用 'extra_data' 代替
    extra_data = Column(JSONB)

    
    def __repr__(self):
        return f"<Call {self.id} - {self.counterpart} ({self.status}/{self.handler_type})>"
    
    @property
    def actual_duration(self) -> int:
        """Calculate actual call duration."""
        if self.answered_at and self.ended_at:
            return int((self.ended_at - self.answered_at).total_seconds())
        return 0
    
    @property
    def wait_time(self) -> int:
        """Calculate wait time before answer."""
        if self.started_at and self.answered_at:
            return int((self.answered_at - self.started_at).total_seconds())
        return 0
