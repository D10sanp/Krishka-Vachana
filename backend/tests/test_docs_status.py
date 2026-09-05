from app.core.config import Settings, get_settings
from app.core.firebase import FirebaseState, get_firebase_state
from app.main import app


class _ConfiguredFirebase(FirebaseState):
    @property
    def is_configured(self) -> bool:
        return True


def test_custom_docs_page_served(client):
    """Verify that the custom Swagger docs page is served."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger-ui" in response.text.lower()


def test_redoc_page_served(client):
    """Verify that the ReDoc page is served."""
    response = client.get("/redoc")
    assert response.status_code == 200


def test_openapi_schema_available(client):
    """Verify that the OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Krishka Vachana API"


def test_status_page_served(client):
    """Verify that the status page is served."""
    response = client.get("/status")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Service status" in response.text
    assert '<span class="badge badge-warn">not configured</span>' in response.text
    assert "in-memory fallback" not in response.text

    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="development", allow_dev_auth_fallback=True
    )
    response = client.get("/status")
    assert '<span class="badge badge-warn">using in-memory fallback</span>' in response.text


def test_status_page_labels_configured_firebase(client):
    """Verify that the status page shows Firebase as configured when available."""
    app.dependency_overrides[get_firebase_state] = lambda: _ConfiguredFirebase()
    response = client.get("/status")
    assert response.status_code == 200
    assert '<span class="badge badge-ok">configured</span>' in response.text
    assert "connected" not in response.text


def test_status_page_labels_congestion_prediction_state(client):
    """Verify that the status page shows congestion prediction configuration state."""
    response = client.get("/status")
    assert response.status_code == 200
    assert '<span class="badge badge-warn">using heuristic fallback</span>' in response.text

    app.dependency_overrides[get_settings] = lambda: Settings(
        congestion_prediction_api_url="https://ml.example.com/predict"
    )
    response = client.get("/status")
    assert (
        '<tr><th>Congestion prediction (AI/ML)</th><td>'
        '<span class="badge badge-ok">configured</span></td></tr>'
    ) in response.text
