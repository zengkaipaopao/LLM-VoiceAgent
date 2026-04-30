from app.services.twilio.media_stream_profiles import (
    normalize_media_stream_bridge_profile,
    resolve_media_stream_bridge_profile_contract,
    validate_media_stream_bridge_profile,
)


def test_normalize_media_stream_bridge_profile_resolves_aliases():
    assert normalize_media_stream_bridge_profile("cx") == "cx_agent_studio"
    assert normalize_media_stream_bridge_profile("manual") == "legacy_manual"


def test_resolve_media_stream_bridge_profile_contract_exposes_clear_runtime_ownership():
    contract = resolve_media_stream_bridge_profile_contract("cx_agent_studio")

    assert contract.turn_owner == "backend_manual_boundaries"
    assert contract.duplex_mode == "half_duplex"
    assert contract.interruption_policy == "no_interruption"
    assert contract.overlap_policy == "drop_while_playing"
    assert contract.manual_activity_enabled is True
    assert contract.manual_activity_silence_target_ms == 200


def test_validate_media_stream_bridge_profile_rejects_unknown_values():
    try:
        validate_media_stream_bridge_profile("unknown-profile")
    except ValueError as exc:
        assert "Unsupported TWILIO_MEDIA_STREAM_BRIDGE_PROFILE" in str(exc)
    else:
        raise AssertionError("expected ValueError")

