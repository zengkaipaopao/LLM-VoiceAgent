from app.services.twilio.trace_diagnostics import build_twilio_trace_diagnostic


def test_trace_diagnostic_classifies_missing_adc_error():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA123",
        stream_active=True,
        events=[
            {
                "seq": 1,
                "ts": 1_710_000_000_000,
                "type": "stream_error",
                "level": "error",
                "text": "Your default credentials were not found. To set up Application Default Credentials.",
            }
        ],
    )

    assert diagnostic["status"] == "error"
    assert diagnostic["category"] == "google_adc_missing"
    assert diagnostic["owner"] == "google_cloud_auth"


def test_trace_diagnostic_classifies_vertex_permission_error():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA124",
        stream_active=True,
        events=[
            {
                "seq": 2,
                "ts": 1_710_000_000_000,
                "type": "stream_error",
                "level": "error",
                "text": "1008 None. Permission 'aiplatform.endpoints.predict' denied on resource.",
            }
        ],
    )

    assert diagnostic["status"] == "error"
    assert diagnostic["category"] == "google_vertex_permission"
    assert diagnostic["owner"] == "google_cloud_iam"


def test_trace_diagnostic_warns_when_turn_completes_without_audio():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125",
        stream_active=True,
        events=[
            {
                "seq": 3,
                "ts": 1_710_000_000_000,
                "type": "assistant_turn_without_audio",
                "level": "warning",
                "text": "Gemini Live completed a turn without emitting audio parts.",
            }
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "assistant_turn_without_audio"


def test_trace_diagnostic_warns_when_followup_audio_has_no_new_input_transcript():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125A",
        stream_active=True,
        events=[
            {
                "seq": 4,
                "ts": 1_710_000_000_000,
                "type": "gemini_turn_detection_stalled",
                "level": "warning",
                "text": "trigger=followup_probe_full capture_seconds=5 followup_audio_detected_but_no_new_input_transcript",
            }
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "gemini_turn_detection_stalled"
    assert diagnostic["owner"] == "gemini_live_turn_detection"


def test_trace_diagnostic_classifies_duplex_overlap_when_stalled_and_overlap_present():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125B",
        stream_active=True,
        events=[
            {
                "seq": 4,
                "ts": 1_710_000_000_000,
                "type": "duplex_overlap_detected",
                "level": "warning",
                "text": "rms=640 assistant_phase=playback_pending pending_mark=assistant-turn-1",
            },
            {
                "seq": 5,
                "ts": 1_710_000_001_000,
                "type": "gemini_turn_detection_stalled",
                "level": "warning",
                "text": "trigger=followup_probe_full capture_seconds=5 followup_audio_detected_but_no_new_input_transcript",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "duplex_overlap_vad_conflict"
    assert diagnostic["owner"] == "duplex_audio_path"


def test_trace_diagnostic_manual_boundary_mode_mentions_manual_activity_boundaries():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125C",
        stream_active=True,
        events=[
            {
                "seq": 3,
                "ts": 1_710_000_000_500,
                "type": "live_runtime_config",
                "level": "info",
                "text": "activity_mode=manual_explicit_boundaries local_turn_segmentation=minimal_manual_activity_boundaries",
            },
            {
                "seq": 4,
                "ts": 1_710_000_000_900,
                "type": "duplex_overlap_detected",
                "level": "warning",
                "text": "rms=311 assistant_phase=playback_pending pending_mark=assistant-turn-1",
            },
            {
                "seq": 5,
                "ts": 1_710_000_001_000,
                "type": "gemini_turn_detection_stalled",
                "level": "warning",
                "text": "trigger=followup_probe_full capture_seconds=5 followup_audio_detected_but_no_new_input_transcript",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "duplex_overlap_vad_conflict"
    assert "手动活动边界" in diagnostic["title"]
    assert "manual_activity_start_sent" in " ".join(diagnostic["actions"])


def test_trace_diagnostic_manual_boundary_mode_detects_missing_activity_end_after_playback():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125D",
        stream_active=True,
        events=[
            {
                "seq": 3,
                "ts": 1_710_000_000_500,
                "type": "live_runtime_config",
                "level": "info",
                "text": "activity_mode=manual_explicit_boundaries manual_end_rms=110",
            },
            {
                "seq": 4,
                "ts": 1_710_000_000_600,
                "type": "duplex_overlap_detected",
                "level": "warning",
                "text": "rms=196 assistant_phase=playback_pending pending_mark=assistant-turn-1",
            },
            {
                "seq": 5,
                "ts": 1_710_000_001_000,
                "type": "playback_complete",
                "level": "success",
                "text": "assistant-turn-1",
            },
            {
                "seq": 6,
                "ts": 1_710_000_001_010,
                "type": "manual_activity_start_sent",
                "level": "info",
                "text": "rms=396 threshold=100 prefix_ms=100 mode=normal_after_playback",
            },
            {
                "seq": 7,
                "ts": 1_710_000_006_000,
                "type": "gemini_turn_detection_stalled",
                "level": "warning",
                "text": "trigger=followup_probe_full capture_seconds=5 followup_audio_detected_but_no_new_input_transcript",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "manual_activity_end_missing"
    assert "结束边界" in diagnostic["title"]
    assert "manual_end_rms" in " ".join(diagnostic["actions"])


def test_trace_diagnostic_prefers_manual_activity_end_overdue_evidence_when_present():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA125E",
        stream_active=True,
        events=[
            {
                "seq": 3,
                "ts": 1_710_000_000_500,
                "type": "live_runtime_config",
                "level": "info",
                "text": "activity_mode=manual_explicit_boundaries input_gate=on manual_end_rms=110",
            },
            {
                "seq": 4,
                "ts": 1_710_000_001_000,
                "type": "playback_complete",
                "level": "success",
                "text": "assistant-turn-1",
            },
            {
                "seq": 5,
                "ts": 1_710_000_001_010,
                "type": "manual_activity_start_sent",
                "level": "info",
                "text": "raw_rms=396 conditioned_rms=388 threshold=100 end_threshold=110 prefix_ms=100 mode=normal_after_playback",
            },
            {
                "seq": 6,
                "ts": 1_710_000_006_000,
                "type": "manual_activity_end_overdue",
                "level": "warning",
                "text": "reason=followup_probe_full_no_input_transcript elapsed_ms=4980 silence_ms=120 silence_target_ms=800 last_raw_rms=124 last_conditioned_rms=124 peak_raw_rms=396 lowest_conditioned_rms=92 end_rms=110",
            },
            {
                "seq": 7,
                "ts": 1_710_000_006_001,
                "type": "gemini_turn_detection_stalled",
                "level": "warning",
                "text": "trigger=followup_probe_full capture_seconds=5 followup_audio_detected_but_no_new_input_transcript",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "manual_activity_end_missing"
    assert diagnostic["owner"] == "client_activity_boundaries"
    assert diagnostic["evidence"][0]["type"] == "manual_activity_end_overdue"


def test_trace_diagnostic_warns_when_stream_active_without_assistant_audio():
    base_ts = 1_710_000_000_000
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA126",
        stream_active=True,
        events=[
            {
                "seq": 1,
                "ts": base_ts - 12_000,
                "type": "stream_start",
                "level": "success",
                "text": "prompt=base_appointment voice=Aoede activity_mode=auto",
            },
            {
                "seq": 2,
                "ts": base_ts - 10_000,
                "type": "opening_turn_requested",
                "level": "info",
                "text": "Requested Gemini Live opening greeting",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "assistant_not_responding"


def test_trace_diagnostic_warns_when_upstream_audio_has_no_turn_or_reply():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA126A",
        stream_active=False,
        events=[
            {
                "seq": 1,
                "ts": 1_710_000_000_000,
                "type": "audio_stream_resumed",
                "level": "info",
                "text": "conditioned_rms=279",
            },
            {
                "seq": 2,
                "ts": 1_710_000_001_000,
                "type": "audio_stream_end_sent",
                "level": "info",
                "text": "silence_ms=1014 conditioned_rms=0",
            },
            {
                "seq": 3,
                "ts": 1_710_000_002_000,
                "type": "stream_stop",
                "level": "info",
                "text": "",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "upstream_audio_without_turn"
    assert diagnostic["owner"] == "gemini_live_turn_detection"


def test_trace_diagnostic_warns_when_assistant_started_but_no_audio_flow_progress():
    diagnostic = build_twilio_trace_diagnostic(
        call_sid="CA127",
        stream_active=True,
        events=[
            {
                "seq": 1,
                "ts": 1_710_000_000_000,
                "type": "stream_start",
                "level": "success",
                "text": "prompt=base_appointment voice=Aoede activity_mode=auto",
            },
            {
                "seq": 2,
                "ts": 1_710_000_000_500,
                "type": "assistant_audio_started",
                "level": "success",
                "text": "audio/pcm;rate=24000",
            },
        ],
    )

    assert diagnostic["status"] == "warning"
    assert diagnostic["category"] == "assistant_not_responding"
