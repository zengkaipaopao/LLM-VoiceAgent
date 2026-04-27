from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.services.twilio.media_stream_profiles import (
    TwilioMediaBridgeProfile,
    resolve_media_stream_bridge_profile_contract,
)


@dataclass(frozen=True, slots=True)
class TwilioMediaStreamRuntimeConfig:
    bridge_profile: str
    bridge_profile_contract: TwilioMediaBridgeProfile
    requested_manual_vad: bool
    legacy_manual_vad: bool
    half_duplex_manual_turn_control: bool
    manual_activity_control: bool
    auto_vad_prefix_padding_ms: int
    auto_vad_silence_duration_ms: int
    input_noise_gate_enabled: bool
    input_noise_gate_hold_ms: int
    input_gate_open_rms: int
    input_gate_close_rms: int
    inbound_batch_ms: int
    manual_start_rms: int
    manual_end_rms: int
    manual_start_hits_required: int
    manual_barge_rms: int
    manual_barge_hits_required: int
    manual_silence_target_ms: int
    manual_silence_hits_required: int

    @property
    def activity_mode_log_label(self) -> str:
        if self.half_duplex_manual_turn_control:
            return "manual_half_duplex"
        if self.legacy_manual_vad:
            return "manual"
        return "auto"

    @property
    def trace_activity_mode(self) -> str:
        if self.half_duplex_manual_turn_control:
            return "manual_half_duplex_boundaries"
        if self.legacy_manual_vad:
            return "manual_explicit_boundaries"
        return "auto_server_vad"

    @property
    def effective_activity_handling(self) -> str:
        if self.half_duplex_manual_turn_control:
            return "backend_owned_no_interruption"
        if self.legacy_manual_vad:
            return "client_owned"
        return settings.twilio_gemini_activity_handling or "-"

    @property
    def effective_turn_coverage(self) -> str:
        if self.half_duplex_manual_turn_control:
            return "all_input"
        if self.legacy_manual_vad:
            return "client_owned"
        return settings.twilio_gemini_turn_coverage or "-"

    @property
    def interruption_source(self) -> str:
        if self.half_duplex_manual_turn_control:
            return "disabled"
        if self.legacy_manual_vad:
            return "model_or_local_barge_in"
        return "model_only"

    @property
    def local_overlap_gate(self) -> str:
        return "drop_while_playing" if self.half_duplex_manual_turn_control else "off"

    @property
    def local_turn_segmentation(self) -> str:
        if self.half_duplex_manual_turn_control:
            return f"half_duplex_manual_activity_end_{self.manual_silence_target_ms}ms"
        if self.legacy_manual_vad:
            return "minimal_manual_activity_boundaries"
        return "off"

    @property
    def effective_prefix_padding_ms(self) -> int:
        if self.manual_activity_control:
            return settings.twilio_gemini_prefix_padding_ms
        return self.auto_vad_prefix_padding_ms

    @property
    def effective_silence_duration_ms(self) -> int:
        if self.manual_activity_control:
            return self.manual_silence_target_ms
        return self.auto_vad_silence_duration_ms


def build_twilio_media_stream_runtime_config(
    *,
    bridge_profile: str,
    requested_manual_vad: bool,
    duplex_overlap_rms_threshold: int,
    followup_probe_rms_threshold: int,
    twilio_media_frame_ms: int,
) -> TwilioMediaStreamRuntimeConfig:
    bridge_profile_contract = resolve_media_stream_bridge_profile_contract(bridge_profile)
    legacy_manual_vad = requested_manual_vad and bridge_profile_contract.name == "legacy_manual"
    half_duplex_manual_turn_control = (
        bridge_profile_contract.manual_activity_enabled
        and bridge_profile_contract.name == "cx_agent_studio"
    )
    manual_activity_control = legacy_manual_vad or half_duplex_manual_turn_control
    auto_vad_prefix_padding_ms = (
        0 if manual_activity_control else settings.twilio_gemini_prefix_padding_ms
    )
    auto_vad_silence_duration_ms = (
        0 if manual_activity_control else settings.twilio_gemini_silence_duration_ms
    )
    input_noise_gate_enabled = (
        settings.twilio_media_stream_input_noise_gate_enabled
        if bridge_profile_contract.enable_input_gate is None
        else bridge_profile_contract.enable_input_gate
    )
    input_noise_gate_hold_ms = (
        bridge_profile_contract.input_gate_hold_ms_override
        if bridge_profile_contract.input_gate_hold_ms_override is not None
        else settings.twilio_media_stream_input_noise_gate_hold_ms
    )
    manual_start_rms = max(
        int(settings.twilio_media_stream_upstream_activity_rms or 0),
        followup_probe_rms_threshold,
    )
    manual_end_rms = max(
        followup_probe_rms_threshold,
        min(140, max(manual_start_rms, int(manual_start_rms * 1.1))),
    )
    manual_silence_target_ms = (
        bridge_profile_contract.manual_activity_silence_target_ms
        if half_duplex_manual_turn_control
        and bridge_profile_contract.manual_activity_silence_target_ms is not None
        else max(0, settings.twilio_gemini_silence_duration_ms)
    )
    manual_silence_hits_required = max(
        2,
        int(manual_silence_target_ms / twilio_media_frame_ms),
    )
    return TwilioMediaStreamRuntimeConfig(
        bridge_profile=bridge_profile,
        bridge_profile_contract=bridge_profile_contract,
        requested_manual_vad=requested_manual_vad,
        legacy_manual_vad=legacy_manual_vad,
        half_duplex_manual_turn_control=half_duplex_manual_turn_control,
        manual_activity_control=manual_activity_control,
        auto_vad_prefix_padding_ms=auto_vad_prefix_padding_ms,
        auto_vad_silence_duration_ms=auto_vad_silence_duration_ms,
        input_noise_gate_enabled=input_noise_gate_enabled,
        input_noise_gate_hold_ms=input_noise_gate_hold_ms,
        input_gate_open_rms=max(0, int(settings.twilio_media_stream_input_noise_gate_open_rms or 0)),
        input_gate_close_rms=max(
            0,
            int(settings.twilio_media_stream_input_noise_gate_close_rms or 0),
        ),
        inbound_batch_ms=max(0, int(settings.twilio_media_stream_inbound_batch_ms or 0)),
        manual_start_rms=manual_start_rms,
        manual_end_rms=manual_end_rms,
        manual_start_hits_required=2,
        manual_barge_rms=max(900, duplex_overlap_rms_threshold * 4),
        manual_barge_hits_required=4,
        manual_silence_target_ms=manual_silence_target_ms,
        manual_silence_hits_required=manual_silence_hits_required,
    )
