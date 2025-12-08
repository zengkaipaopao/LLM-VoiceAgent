from datetime import datetime

from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    voice: str | None = None
    speaking_rate: float | None = None
    noise_suppression: bool | None = None


class PromptCapabilities(BaseModel):
    appointment_logging: bool = False


class PromptTemplate(BaseModel):
    id: str
    name: str
    model_id: str
    system_prompt: str
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    updated_at: datetime
    version: str
    capabilities: PromptCapabilities = Field(default_factory=PromptCapabilities)


class PromptCreate(BaseModel):
    name: str
    model_id: str
    system_prompt: str
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    version: str
    capabilities: PromptCapabilities | None = None


class PromptUpdate(BaseModel):
    name: str | None = None
    model_id: str | None = None
    system_prompt: str | None = None
    welcome_message: str | None = None
    voice_config: VoiceConfig | None = None
    version: str | None = None
    capabilities: PromptCapabilities | None = None
