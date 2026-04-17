from google.genai import types

from app.core.config import settings


def _use_manual_vad_control() -> bool:
    mode = (settings.twilio_gemini_activity_mode or "auto").strip().lower()
    return mode in {"manual", "manual_vad", "explicit"}


def _validate_twilio_activity_mode() -> None:
    mode = (settings.twilio_gemini_activity_mode or "auto").strip().lower()
    if mode in {"", "auto"}:
        return
    raise ValueError(
        "Twilio Media Streams production path only supports Gemini automatic activity detection. "
        "Set TWILIO_GEMINI_ACTIVITY_MODE=auto."
    )


def _resolve_activity_handling() -> types.ActivityHandling | None:
    token = (settings.twilio_gemini_activity_handling or "").strip().lower()
    mapping = {
        "interrupt": types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        "interrupts": types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        "start_of_activity_interrupts": types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        "barge_in": types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        "no_interrupt": types.ActivityHandling.NO_INTERRUPTION,
        "no_interruption": types.ActivityHandling.NO_INTERRUPTION,
        "none": types.ActivityHandling.NO_INTERRUPTION,
    }
    return mapping.get(token)


def _resolve_turn_coverage() -> types.TurnCoverage | None:
    token = (settings.twilio_gemini_turn_coverage or "").strip().lower()
    mapping = {
        "activity": types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
        "activity_only": types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
        "only_activity": types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
        "all": types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
        "all_input": types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
        "includes_all_input": types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
    }
    return mapping.get(token)


def _resolve_start_sensitivity() -> types.StartSensitivity | None:
    token = (settings.twilio_gemini_start_sensitivity or "").strip().lower()
    mapping = {
        "high": types.StartSensitivity.START_SENSITIVITY_HIGH,
        "low": types.StartSensitivity.START_SENSITIVITY_LOW,
    }
    return mapping.get(token)


def _resolve_end_sensitivity() -> types.EndSensitivity | None:
    token = (settings.twilio_gemini_end_sensitivity or "").strip().lower()
    mapping = {
        "high": types.EndSensitivity.END_SENSITIVITY_HIGH,
        "low": types.EndSensitivity.END_SENSITIVITY_LOW,
    }
    return mapping.get(token)


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
    speech_config_payload: dict[str, object] = {}
    language_code = (settings.twilio_agent_language or "").strip()
    if language_code:
        speech_config_payload["language_code"] = language_code
    if voice_name:
        speech_config_payload["voice_config"] = {
            "prebuilt_voice_config": {
                "voice_name": voice_name,
            }
        }
    if speech_config_payload:
        payload["speech_config"] = speech_config_payload
    if system_instruction:
        payload["system_instruction"] = system_instruction

    auto_detection = types.AutomaticActivityDetection(disabled=manual_vad)
    if not manual_vad:
        start_sensitivity = _resolve_start_sensitivity()
        end_sensitivity = _resolve_end_sensitivity()
        prefix_padding_ms = max(0, int(settings.twilio_gemini_prefix_padding_ms or 0))
        silence_duration_ms = max(0, int(settings.twilio_gemini_silence_duration_ms or 0))
        if start_sensitivity is not None:
            auto_detection.start_of_speech_sensitivity = start_sensitivity
        if end_sensitivity is not None:
            auto_detection.end_of_speech_sensitivity = end_sensitivity
        if prefix_padding_ms > 0:
            auto_detection.prefix_padding_ms = prefix_padding_ms
        if silence_duration_ms > 0:
            auto_detection.silence_duration_ms = silence_duration_ms

    realtime_input_config = types.RealtimeInputConfig(
        automatic_activity_detection=auto_detection,
    )
    if not manual_vad:
        activity_handling = _resolve_activity_handling()
        turn_coverage = _resolve_turn_coverage()
        if activity_handling is not None:
            realtime_input_config.activity_handling = activity_handling
        if turn_coverage is not None:
            realtime_input_config.turn_coverage = turn_coverage
    payload["realtime_input_config"] = realtime_input_config

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
