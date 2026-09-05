from app import create_app


def test_health_endpoint_requires_no_external_services():
    app = create_app()

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "service": "improv-faceoff-backend",
        "status": "ok",
    }
