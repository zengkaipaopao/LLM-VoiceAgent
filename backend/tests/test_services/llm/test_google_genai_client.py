from app.services import google_genai_client


def test_prepare_google_genai_environment_exports_credentials_path(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(
        google_genai_client,
        "settings",
        type(
            "StubSettings",
            (),
            {
                "google_application_credentials": "/tmp/demo-vertex-creds.json",
                "google_genai_allow_api_key_fallback": True,
                "google_vertex_enabled": True,
                "google_genai_use_vertexai": True,
                "google_api_key": "",
                "google_cloud_project": "demo-project",
                "google_cloud_location": "global",
            },
        )(),
    )

    google_genai_client.prepare_google_genai_environment()

    assert google_genai_client.os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/tmp/demo-vertex-creds.json"


def test_google_genai_available_with_api_key(monkeypatch):
    monkeypatch.setattr(
        google_genai_client,
        "settings",
        type(
            "StubSettings",
            (),
            {
                "google_application_credentials": "",
                "google_genai_allow_api_key_fallback": True,
                "google_vertex_enabled": False,
                "google_genai_use_vertexai": False,
                "google_api_key": "test-key",
                "google_cloud_project": "",
                "google_cloud_location": "global",
            },
        )(),
    )

    available, reason = google_genai_client.google_genai_available()

    assert available is True
    assert reason is None


def test_google_genai_available_with_vertex(monkeypatch):
    monkeypatch.setattr(
        google_genai_client,
        "settings",
        type(
            "StubSettings",
            (),
            {
                "google_application_credentials": "/tmp/demo-vertex-creds.json",
                "google_genai_allow_api_key_fallback": True,
                "google_vertex_enabled": True,
                "google_genai_use_vertexai": True,
                "google_api_key": "",
                "google_cloud_project": "demo-project",
                "google_cloud_location": "global",
            },
        )(),
    )

    available, reason = google_genai_client.google_genai_available()

    assert available is True
    assert reason is None


def test_create_google_genai_client_uses_vertex_when_enabled(monkeypatch):
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        google_genai_client,
        "settings",
        type(
            "StubSettings",
            (),
            {
                "google_application_credentials": "/tmp/demo-vertex-creds.json",
                "google_genai_allow_api_key_fallback": True,
                "google_vertex_enabled": True,
                "google_genai_use_vertexai": True,
                "google_api_key": "",
                "google_cloud_project": "demo-project",
                "google_cloud_location": "global",
            },
        )(),
    )
    monkeypatch.setattr(google_genai_client.genai, "Client", DummyClient)

    google_genai_client.create_google_genai_client(api_version="v1beta1")

    assert captured["vertexai"] is True
    assert captured["project"] == "demo-project"
    assert captured["location"] == "global"
    assert captured["http_options"].api_version == "v1beta1"


def test_create_google_genai_client_uses_api_key_fallback(monkeypatch):
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        google_genai_client,
        "settings",
        type(
            "StubSettings",
            (),
            {
                "google_application_credentials": "",
                "google_genai_allow_api_key_fallback": True,
                "google_vertex_enabled": False,
                "google_genai_use_vertexai": False,
                "google_api_key": "test-key",
                "google_cloud_project": "",
                "google_cloud_location": "global",
            },
        )(),
    )
    monkeypatch.setattr(google_genai_client.genai, "Client", DummyClient)

    google_genai_client.create_google_genai_client()

    assert captured["api_key"] == "test-key"
