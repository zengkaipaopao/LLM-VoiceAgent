from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TurnOwner = Literal["gemini_server_vad", "backend_manual_boundaries"]
DuplexMode = Literal["half_duplex", "full_duplex"]
InterruptionPolicy = Literal["no_interruption", "model_only", "local_barge_in"]
OverlapPolicy = Literal["drop_while_playing", "clear_and_replay", "passthrough"]


@dataclass(frozen=True, slots=True)
class TwilioMediaBridgeProfile:
    name: str
    label: str
    turn_owner: TurnOwner
    duplex_mode: DuplexMode
    interruption_policy: InterruptionPolicy
    overlap_policy: OverlapPolicy
    enable_input_gate: bool | None = None
    input_gate_hold_ms_override: int | None = None
    manual_activity_enabled: bool = False
    manual_activity_silence_target_ms: int | None = None


_PROFILE_ALIASES = {
    "cx": "cx_agent_studio",
    "cx_agent_studio": "cx_agent_studio",
    "cx-agent-studio": "cx_agent_studio",
    "official_like": "cx_agent_studio",
    "official": "cx_agent_studio",
    "thin_bridge": "cx_agent_studio",
    "legacy": "legacy_manual",
    "legacy_manual": "legacy_manual",
    "manual": "legacy_manual",
}

_PROFILE_REGISTRY: dict[str, TwilioMediaBridgeProfile] = {
    "cx_agent_studio": TwilioMediaBridgeProfile(
        name="cx_agent_studio",
        label="CX Agent Studio 风格的半双工电话桥",
        turn_owner="backend_manual_boundaries",
        duplex_mode="half_duplex",
        interruption_policy="no_interruption",
        overlap_policy="drop_while_playing",
        enable_input_gate=True,
        input_gate_hold_ms_override=80,
        manual_activity_enabled=True,
        manual_activity_silence_target_ms=200,
    ),
    "legacy_manual": TwilioMediaBridgeProfile(
        name="legacy_manual",
        label="遗留手动活动边界桥",
        turn_owner="backend_manual_boundaries",
        duplex_mode="half_duplex",
        interruption_policy="local_barge_in",
        overlap_policy="clear_and_replay",
        manual_activity_enabled=True,
    ),
}


def normalize_media_stream_bridge_profile(token: str | None) -> str:
    normalized = (token or "cx_agent_studio").strip().lower()
    return _PROFILE_ALIASES.get(normalized, normalized)


def validate_media_stream_bridge_profile(token: str | None = None) -> None:
    normalized = normalize_media_stream_bridge_profile(token)
    if normalized in _PROFILE_REGISTRY:
        return
    supported = ", ".join(sorted(_PROFILE_REGISTRY))
    raise ValueError(
        "Unsupported TWILIO_MEDIA_STREAM_BRIDGE_PROFILE. "
        f"Supported values: {supported}."
    )


def resolve_media_stream_bridge_profile_contract(token: str | None = None) -> TwilioMediaBridgeProfile:
    normalized = normalize_media_stream_bridge_profile(token)
    try:
        return _PROFILE_REGISTRY[normalized]
    except KeyError as exc:
        validate_media_stream_bridge_profile(normalized)
        raise AssertionError("unreachable") from exc


def list_media_stream_bridge_profiles() -> tuple[str, ...]:
    return tuple(sorted(_PROFILE_REGISTRY))

