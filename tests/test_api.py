from fastapi.testclient import TestClient


def test_liveness_and_security_headers(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-ID": "health-00000001"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Correlation-ID"] == "health-00000001"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_invalid_correlation_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-ID": "bad value"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] != "bad value"
