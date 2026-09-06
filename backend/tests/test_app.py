from app import create_app
from app.config import AppConfig


class UnconfiguredLiveKitConfig(AppConfig):
    LIVEKIT_URL = ""
    LIVEKIT_API_KEY = ""
    LIVEKIT_API_SECRET = ""
    USE_IN_MEMORY_REDIS = True


def test_health_endpoint_requires_no_external_services():
    app = create_app()

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "service": "improv-faceoff-backend",
        "status": "ok",
    }


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
