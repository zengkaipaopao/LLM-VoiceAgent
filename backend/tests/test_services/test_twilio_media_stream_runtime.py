from app.services.twilio import media_stream_runtime


def _build_stub_settings(**overrides):
    defaults = {
        "twilio_gemini_activity_handling": "interrupt",
        "twilio_gemini_turn_coverage": "activity_only",
        "twilio_gemini_prefix_padding_ms": 100,
        "twilio_gemini_silence_duration_ms": 800,
        "twilio_media_stream_input_noise_gate_enabled": True,
        "twilio_media_stream_input_noise_gate_open_rms": 140,
        "twilio_media_stream_input_noise_gate_close_rms": 90,
        "twilio_media_stream_input_noise_gate_hold_ms": 240,
        "twilio_media_stream_inbound_batch_ms": 20,
        "twilio_media_stream_upstream_activity_rms": 48,
    }
    defaults.update(overrides)
    return type("StubSettings", (), defaults)()


def test_build_runtime_config_for_cx_agent_studio_owns_half_duplex_boundaries(monkeypatch):
    monkeypatch.setattr(
        media_stream_runtime,
        "settings",
        _build_stub_settings(),
    )

    runtime = media_stream_runtime.build_twilio_media_stream_runtime_config(
        bridge_profile="cx_agent_studio",
        requested_manual_vad=False,
        duplex_overlap_rms_threshold=180,
        followup_probe_rms_threshold=100,
        twilio_media_frame_ms=20,
    )

    assert runtime.half_duplex_manual_turn_control is True
    assert runtime.manual_activity_control is True
    assert runtime.activity_mode_log_label == "manual_half_duplex"
    assert runtime.trace_activity_mode == "manual_half_duplex_boundaries"
    assert runtime.effective_activity_handling == "backend_owned_no_interruption"
    assert runtime.effective_turn_coverage == "all_input"
    assert runtime.local_overlap_gate == "drop_while_playing"
    assert runtime.local_turn_segmentation == "half_duplex_manual_activity_end_200ms"
    assert runtime.input_noise_gate_enabled is True
    assert runtime.input_noise_gate_hold_ms == 80
    assert runtime.effective_prefix_padding_ms == 100
    assert runtime.effective_silence_duration_ms == 200


def test_build_runtime_config_for_legacy_manual_preserves_local_barge_in(monkeypatch):
    monkeypatch.setattr(
        media_stream_runtime,
        "settings",
        _build_stub_settings(
            twilio_gemini_activity_handling="interrupt",
            twilio_gemini_turn_coverage="activity_only",
        ),
    )

    runtime = media_stream_runtime.build_twilio_media_stream_runtime_config(
        bridge_profile="legacy_manual",
        requested_manual_vad=True,
        duplex_overlap_rms_threshold=180,
        followup_probe_rms_threshold=100,
        twilio_media_frame_ms=20,
    )

    assert runtime.legacy_manual_vad is True
    assert runtime.manual_activity_control is True
    assert runtime.activity_mode_log_label == "manual"
    assert runtime.trace_activity_mode == "manual_explicit_boundaries"
    assert runtime.effective_activity_handling == "client_owned"
    assert runtime.effective_turn_coverage == "client_owned"
    assert runtime.interruption_source == "model_or_local_barge_in"
    assert runtime.local_turn_segmentation == "minimal_manual_activity_boundaries"
    assert runtime.effective_silence_duration_ms == 800


def test_build_runtime_config_for_auto_profile_keeps_upstream_vad(monkeypatch):
    monkeypatch.setattr(
        media_stream_runtime,
        "settings",
        _build_stub_settings(
            twilio_gemini_activity_handling="no_interruption",
            twilio_gemini_turn_coverage="all_input",
        ),
    )

    runtime = media_stream_runtime.build_twilio_media_stream_runtime_config(
        bridge_profile="legacy_manual",
        requested_manual_vad=False,
        duplex_overlap_rms_threshold=180,
        followup_probe_rms_threshold=100,
        twilio_media_frame_ms=20,
    )

    assert runtime.manual_activity_control is False
    assert runtime.activity_mode_log_label == "auto"
    assert runtime.trace_activity_mode == "auto_server_vad"
    assert runtime.effective_activity_handling == "no_interruption"
    assert runtime.effective_turn_coverage == "all_input"
    assert runtime.effective_prefix_padding_ms == 100
    assert runtime.effective_silence_duration_ms == 800
