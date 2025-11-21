from datetime import datetime

from pydantic import BaseModel, Field


class CallLog(BaseModel):
    id: str
    direction: str = Field(description="inbound or outbound")
    counterpart: str
    started_at: datetime
    duration_seconds: int
    status: str
    summary: str | None = None


class CallCreate(BaseModel):
    counterpart: str
    agent_id: str
    prompt_id: str
    metadata: dict | None = None


class PaginatedCallResponse(BaseModel):
    data: list[CallLog]
    total: int
