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
