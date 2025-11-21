from datetime import datetime

from pydantic import BaseModel


class PromptTemplate(BaseModel):
    id: str
    name: str
    system_prompt: str
    updated_at: datetime
    version: str


class PromptUpdate(BaseModel):
    system_prompt: str
