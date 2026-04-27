from app.services.twilio.manual_activity_controller import TwilioManualActivityController


def _build_controller() -> TwilioManualActivityController:
    return TwilioManualActivityController(
        frame_ms=20,
        prefix_padding_ms=100,
        start_rms=100,
        end_rms=110,
        start_hits_required=2,
        barge_rms=900,
        barge_hits_required=4,
        silence_hits_required=3,
        silence_reset_trace_ms=200,
        progress_trace_interval_seconds=0.75,
    )


def test_manual_activity_controller_starts_after_sustained_energy_and_ends_after_silence():
    controller = _build_controller()
    frame = b"\x00\x01" * 320

    assert controller.observe_normal_start_candidate(pcm16k=frame, raw_rms=120) is None
    prefix_payload = controller.observe_normal_start_candidate(pcm16k=frame, raw_rms=130)
    assert prefix_payload is not None

    controller.begin_activity(now_ts=10.0, raw_rms=130, conditioned_rms=130)
    first = controller.observe_active_frame(now_ts=10.1, raw_rms=90, conditioned_rms=90)
    second = controller.observe_active_frame(now_ts=10.2, raw_rms=80, conditioned_rms=80)
    third = controller.observe_active_frame(now_ts=10.3, raw_rms=70, conditioned_rms=70)

    assert first.end_due is False
    assert second.end_due is False
    assert third.end_due is True
    assert third.silence_ms == 60


def test_manual_activity_controller_reports_silence_reset_when_voice_resumes():
    controller = _build_controller()
    controller.begin_activity(now_ts=1.0, raw_rms=130, conditioned_rms=130)

    for index in range(10):
        observation = controller.observe_active_frame(
            now_ts=1.1 + (index * 0.02),
            raw_rms=80,
            conditioned_rms=80,
        )
    assert observation.silence_reset_ms is None

    resumed = controller.observe_active_frame(
        now_ts=1.4,
        raw_rms=180,
        conditioned_rms=180,
    )
    assert resumed.silence_reset_ms == 200
    assert resumed.end_due is False
