from fastapi.testclient import TestClient

from idml_foundation.ingest.scanner import ClamAVScanner, PolicyOnlyScanner, build_scanner
from idml_foundation.settings import Settings


def test_scanner_factory_defaults_to_policy(settings: Settings) -> None:
    assert isinstance(build_scanner(settings), PolicyOnlyScanner)
    result = build_scanner(settings).scan(b"safe")
    assert result.clean
    assert result.status == "policy_only"


def test_scanner_factory_supports_clamav(settings: Settings) -> None:
    configured = settings.model_copy(update={"feature_clamav": True})
    assert isinstance(build_scanner(configured), ClamAVScanner)


def test_readiness_reports_redis_failure_without_leaking_details(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["redis"] == "failed"
    assert "127.0.0.1" not in response.text


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "idml_http_requests_total" in response.text
