from __future__ import annotations

from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, description="需要合成的文本内容")
    model: str = Field(default="gpt-4o-mini-tts", description="OpenAI TTS 模型 ID")
    voice: str = Field(default="alloy", description="可选语音预设")
    format: str = Field(default="mp3", description="音频格式，例如 mp3 / wav / ogg")


class TtsResponse(BaseModel):
    audio_base64: str
    content_type: str
