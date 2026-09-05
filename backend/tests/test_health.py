import logging

from app.core.config import Settings, get_settings
from app.core.firebase import FirebaseState, get_firebase_state
from app.main import app


class _ConfiguredFailingFirebase(FirebaseState):
    @property
    def is_configured(self) -> bool:
        return True

    def firestore_client(self):
        """Mock method for Firestore client."""
        raise RuntimeError("private credential detail")


def test_liveness_check(client):
    """Verify that the liveness endpoint returns service information."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "krishka-vachana-backend"
    assert "version" in body
    assert "uptime_seconds" in body


def test_readiness_check_without_firebase_configured(client):
    """Verify that readiness check reports Firestore as not configured."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body == {"status": "degraded", "checks": {"firestore": "not_configured"}}


def test_readiness_allows_explicit_development_fallback(client):
    """Verify that readiness allows dev fallback when configured."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development", allow_dev_auth_fallback=True
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"firestore": "not_configured (using in-memory fallback)"},
    }


def test_readiness_rejects_fallback_outside_development(client):
    """Verify that readiness rejects dev fallback in production."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="production", allow_dev_auth_fallback=True
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["firestore"] == "not_configured"


def test_readiness_hides_firestore_exception(client, caplog):
    """Verify that readiness returns degraded status when Firestore errors."""
    app.dependency_overrides[get_firebase_state] = lambda: _ConfiguredFailingFirebase()
    with caplog.at_level(logging.ERROR, logger="app.health"):
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": {"firestore": "error"}}
    assert "private credential detail" not in response.text
    assert "private credential detail" in caplog.text


def test_root(client):
    """Verify that the root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Krishka Vachana API"
    assert body["health"] == "/api/v1/health"
