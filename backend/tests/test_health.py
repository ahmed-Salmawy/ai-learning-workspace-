from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "ai-learning-workspace"


def test_health_response_has_correlation_id_header() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.headers["X-Correlation-ID"]
    assert response.json()["correlationId"] == response.headers["X-Correlation-ID"]
