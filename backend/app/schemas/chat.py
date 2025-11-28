from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    model_id: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    model_id: str
    reply: str
