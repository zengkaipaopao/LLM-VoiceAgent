from datetime import datetime

from pydantic import BaseModel


class VoiceConfig(BaseModel):
    voice: str | None = None
    speaking_rate: float | None = None
    noise_suppression: bool | None = None


class PromptTemplate(BaseModel):
    id: str
    name: str
    model_id: str
    system_prompt: str
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    updated_at: datetime
    version: str


class PromptCreate(BaseModel):
    name: str
    model_id: str
    system_prompt: str
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    version: str


class PromptUpdate(BaseModel):
    name: str | None = None
    model_id: str | None = None
    system_prompt: str | None = None
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    version: str | None = None
