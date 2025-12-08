from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TtsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: Literal["openai", "google"] = Field(default="openai", description="TTS 提供商")
    text: str = Field(min_length=1, description="需要合成的文本内容")
    model: str = Field(default="gpt-4o-mini-tts", description="TTS 模型 ID")
    voice: str = Field(default="alloy", description="可选语音预设或 voice name")
    language_code: str | None = Field(
        default=None, description="语音语言代码（Google TTS 可选）", alias="languageCode"
    )
    format: str = Field(default="mp3", description="音频格式，例如 mp3 / wav / ogg")
    speaking_rate: float | None = Field(
        default=None, ge=0.25, le=4.0, description="发音语速（Google TTS 可选，0.25-4.0）", alias="speakingRate"
    )
    pitch: float | None = Field(
        default=None, ge=-20.0, le=20.0, description="音调微调（Google TTS 可选，单位 semitone）"
    )


class TtsResponse(BaseModel):
    audio_base64: str
    content_type: str
