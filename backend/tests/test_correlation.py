from fastapi.testclient import TestClient

from app.core.correlation import get_correlation_id, new_correlation_id
from app.main import app


def test_incoming_correlation_id_is_echoed() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-ID": "test-correlation-123"})

    assert response.headers["X-Correlation-ID"] == "test-correlation-123"
    assert response.json()["correlationId"] == "test-correlation-123"


def test_missing_correlation_id_is_generated() -> None:
    client = TestClient(app)
    first = client.get("/health")
    second = client.get("/health")

    assert first.headers["X-Correlation-ID"]
    assert second.headers["X-Correlation-ID"]
    assert first.headers["X-Correlation-ID"] != second.headers["X-Correlation-ID"]


def test_invalid_correlation_id_is_replaced() -> None:
    client = TestClient(app)
    too_long = "x" * 100
    response = client.get("/health", headers={"X-Correlation-ID": "has spaces"})

    assert response.headers["X-Correlation-ID"] not in {"has spaces", too_long}
    assert get_correlation_id() is None


def test_new_correlation_id_is_unique() -> None:
    assert new_correlation_id() != new_correlation_id()
    assert len(new_correlation_id()) == 32
