from app.core.config import settings
from app.services.twilio.debug_audio_capture import RollingPcmCapture

_PCM8K_RAW_DEBUG_VARIANT = "pcm8k_raw"
_PCM16K_RESAMPLED_DEBUG_VARIANT = "pcm16k_resampled"
_PCM8K_RAW_DEBUG_ARTIFACT = "inbound-pcm8k-raw"
_PCM16K_RESAMPLED_DEBUG_ARTIFACT = "inbound-pcm16k-resampled"
_FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT = "followup_pcm8k_raw"
_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT = "followup_pcm16k_resampled"
_FOLLOWUP_PCM8K_RAW_DEBUG_ARTIFACT = "followup-pcm8k-raw"
_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_ARTIFACT = "followup-pcm16k-resampled"


def _build_debug_capture(*, sample_rate: int, artifact_key: str) -> RollingPcmCapture:
    duration_seconds = max(1, settings.twilio_media_stream_debug_inbound_wav_seconds)
    return RollingPcmCapture(
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        artifact_key=artifact_key,
    )


def _build_twilio_inbound_debug_capture(variant: str) -> RollingPcmCapture:
    normalized_variant = (variant or "").strip().lower()
    if normalized_variant == _PCM8K_RAW_DEBUG_VARIANT:
        return _build_debug_capture(sample_rate=8000, artifact_key=_PCM8K_RAW_DEBUG_ARTIFACT)
    if normalized_variant == _PCM16K_RESAMPLED_DEBUG_VARIANT:
        return _build_debug_capture(
            sample_rate=16000,
            artifact_key=_PCM16K_RESAMPLED_DEBUG_ARTIFACT,
        )
    if normalized_variant == _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT:
        return _build_debug_capture(
            sample_rate=8000,
            artifact_key=_FOLLOWUP_PCM8K_RAW_DEBUG_ARTIFACT,
        )
    if normalized_variant == _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT:
        return _build_debug_capture(
            sample_rate=16000,
            artifact_key=_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_ARTIFACT,
        )
    raise ValueError(f"Unsupported inbound debug audio variant: {variant}")


__all__ = (
    "_build_debug_capture",
    "_build_twilio_inbound_debug_capture",
    "_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT",
    "_FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT",
    "_PCM16K_RESAMPLED_DEBUG_VARIANT",
    "_PCM8K_RAW_DEBUG_VARIANT",
)
