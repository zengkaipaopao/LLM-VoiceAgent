from app.services.twilio.official_conversational_agents import (
    _extract_location_from_resource_name,
    _extract_parent_app_from_deployment_id,
    _looks_like_legacy_agent_resource,
    _looks_like_official_ca_app_resource,
    _looks_like_official_ca_deployment_resource,
    build_official_conversational_agents_stream_parameters,
)


def test_extract_parent_app_from_deployment_id():
    deployment_id = (
        "projects/demo-project/locations/us-central1/apps/demo-app/deployments/demo-deployment"
    )

    assert (
        _extract_parent_app_from_deployment_id(deployment_id)
        == "projects/demo-project/locations/us-central1/apps/demo-app"
    )


def test_extract_location_from_resource_name():
    resource_name = "projects/demo-project/locations/us-central1/apps/demo-app"

    assert _extract_location_from_resource_name(resource_name) == "us-central1"


def test_official_ca_resource_shape_helpers():
    assert _looks_like_official_ca_app_resource(
        "projects/demo-project/locations/us-central1/apps/demo-app"
    )
    assert _looks_like_official_ca_deployment_resource(
        "projects/demo-project/locations/us-central1/apps/demo-app/deployments/demo-deployment"
    )
    assert _looks_like_legacy_agent_resource(
        "projects/demo-project/locations/global/agents/demo-agent"
    )


def test_build_official_conversational_agents_stream_parameters():
    class _Config:
        session_id = "projects/demo-project/locations/us-central1/apps/demo-app/sessions/test-session"
        virtual_agent_endpoint = (
            "wss://ces.googleapis.com/ws/google.cloud.ces.v1.SessionService/"
            "BidiRunSession/locations/us-central1"
        )
        environment = "prod"
        agent_id = "projects/demo-project/locations/us-central1/apps/demo-app"
        deployment_id = (
            "projects/demo-project/locations/us-central1/apps/demo-app/deployments/demo-deployment"
        )

    params = build_official_conversational_agents_stream_parameters(_Config())

    assert params == {
        "ca_session_id": _Config.session_id,
        "ca_virtual_agent_endpoint": _Config.virtual_agent_endpoint,
        "ca_environment": "prod",
        "ca_agent_id": _Config.agent_id,
        "ca_deployment_id": _Config.deployment_id,
    }
