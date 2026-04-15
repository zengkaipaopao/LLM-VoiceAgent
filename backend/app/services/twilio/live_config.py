from google.genai import types

from app.core.config import settings


def _use_manual_vad_control() -> bool:
    mode = (settings.twilio_gemini_activity_mode or "manual").strip().lower()
    return mode in {"manual", "manual_vad", "explicit"}


def _build_gemini_live_config(
    *,
    model: str,
    system_instruction: str | None,
    voice_name: str | None,
    manual_vad: bool,
) -> types.LiveConnectConfig:
    payload: dict[str, object] = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    if voice_name:
        payload["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        }
    if system_instruction:
        payload["system_instruction"] = system_instruction

    payload["realtime_input_config"] = types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            disabled=manual_vad,
        ),
    )

    normalized_model = (model or "").strip().lower()
    if "2.5" in normalized_model:
        payload["thinking_config"] = types.ThinkingConfig(
            thinking_budget=0,
            include_thoughts=False,
        )
    elif "3.1" in normalized_model:
        payload["thinking_config"] = types.ThinkingConfig(
            include_thoughts=False,
            thinking_level="minimal",
        )
    return types.LiveConnectConfig(**payload)
