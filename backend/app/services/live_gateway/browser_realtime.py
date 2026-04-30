"""Browser-facing Gemini Live gateway helpers."""

from __future__ import annotations

import base64
from typing import Any

from google.genai import types

from app.core.database import AsyncSessionLocal
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService

ALLOWED_MODALITIES = {"AUDIO", "TEXT"}


def parse_modalities(raw_value: str | None) -> list[str]:
    if not raw_value:
        return ["AUDIO"]

    modalities = [item.strip().upper() for item in raw_value.split(",") if item.strip()]
    filtered = [item for item in modalities if item in ALLOWED_MODALITIES]
    if not filtered:
        return ["AUDIO"]
    return list(dict.fromkeys(filtered))


def normalize_modalities_for_model(
    model: str,
    modalities: list[str],
) -> tuple[list[str], str | None]:
    """Keep a conservative compatibility guard for preview models."""
    normalized_model = model.lower()
    if "gemini-3.1-flash-live-preview" in normalized_model and modalities != ["AUDIO"]:
        return ["AUDIO"], "This preview model currently runs in AUDIO-only mode in this test tab."
    return modalities, None


def encode_audio_chunk(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, bytes | bytearray | memoryview):
        return base64.b64encode(bytes(data)).decode("ascii")
    if isinstance(data, str):
        return data
    return None


def decode_audio_chunk(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"), validate=True)


def build_live_config(
    *,
    modalities: list[str],
    voice_name: str | None,
    system_instruction: str | None,
) -> types.LiveConnectConfig:
    config_payload = _base_live_config_payload(
        modalities=modalities,
        voice_name=voice_name,
        system_instruction=system_instruction,
    )

    # Browser direct mode streams microphone audio continuously, while Gemini
    # Live owns turn detection. These activity settings keep multi-turn browser
    # conversations responsive without client-owned segmentation.
    config_payload["realtime_input_config"] = types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            disabled=False,
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
            prefix_padding_ms=40,
            silence_duration_ms=200,
        ),
        activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
    )

    return types.LiveConnectConfig(**config_payload)


def build_browser_live_connect_config(
    *,
    modalities: list[str],
    voice_name: str | None,
    system_instruction: str | None,
) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        **_base_live_config_payload(
            modalities=modalities,
            voice_name=voice_name,
            system_instruction=system_instruction,
        )
    )


async def resolve_system_instruction(
    *,
    system_instruction: str | None,
    template_code: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    manual_instruction = (system_instruction or "").strip()
    if manual_instruction:
        return manual_instruction, None, None, None

    code = (template_code or "").strip()
    if not code:
        return None, None, None, None

    async with AsyncSessionLocal() as db:
        prompt_service = PromptService(db)
        runtime = await resolve_prompt_runtime(
            prompt_service,
            template_code=code,
            default_code=code,
            render_system_instruction=True,
            missing_notice=f"Prompt template '{code}' not found or inactive.",
        )
        if not runtime.template:
            return None, f"Prompt template '{code}' not found or inactive.", None, None

        return runtime.system_instruction, runtime.notice, runtime.voice_id, runtime.llm_model


def _base_live_config_payload(
    *,
    modalities: list[str],
    voice_name: str | None,
    system_instruction: str | None,
) -> dict[str, Any]:
    config_payload: dict[str, Any] = {
        "response_modalities": modalities,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }

    if "AUDIO" in modalities and voice_name:
        config_payload["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        }

    if system_instruction:
        config_payload["system_instruction"] = system_instruction

    return config_payload
