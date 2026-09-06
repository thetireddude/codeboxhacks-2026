from app import create_app
from app.config import AppConfig


class UnconfiguredLiveKitConfig(AppConfig):
    GEMINI_API_KEY = ""
    DEEPGRAM_API_KEY = ""
    LIVEKIT_URL = ""
    LIVEKIT_API_KEY = ""
    LIVEKIT_API_SECRET = ""
    USE_IN_MEMORY_REDIS = True


class ReadyConfig(AppConfig):
    GEMINI_API_KEY = "gemini-test-key"
    DEEPGRAM_API_KEY = "deepgram-test-key"
    LIVEKIT_URL = "wss://livekit.example"
    LIVEKIT_API_KEY = "livekit-test-key"
    LIVEKIT_API_SECRET = "livekit-test-secret"
    USE_IN_MEMORY_REDIS = True


def test_health_endpoint_requires_no_external_services():
    app = create_app()

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "service": "improv-faceoff-backend",
        "status": "ok",
    }


def test_readiness_endpoint_identifies_missing_host_configuration_without_secrets():
    app = create_app(UnconfiguredLiveKitConfig)

    response = app.test_client().get("/api/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "service": "improv-faceoff-backend",
        "status": "configuration_required",
        "missing_configuration": [
            "GEMINI_API_KEY",
            "DEEPGRAM_API_KEY",
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
        ],
    }


def test_readiness_endpoint_reports_a_fully_configured_host():
    app = create_app(ReadyConfig)

    response = app.test_client().get("/api/ready")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
    assert response.get_json()["missing_configuration"] == []


def test_livekit_token_endpoint_reports_missing_configuration_without_secrets():
    app = create_app(UnconfiguredLiveKitConfig)

    response = app.test_client().post(
        "/api/matches/00000000-0000-0000-0000-000000000000/livekit-token",
        json={"guest_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "ok": False,
        "error": {
            "code": "LIVEKIT_UNAVAILABLE",
            "message": "LiveKit is not configured",
        },
    }
