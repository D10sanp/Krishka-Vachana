"""Health endpoints for uptime checks and deploy-platform probes.

Two endpoints, matching the standard liveness/readiness split used by most
container platforms (Cloud Run, Kubernetes, etc.):

- GET /health         Liveness: is the process up and able to respond?
                       Always 200 while the app is running. Use this for
                       "is it alive, restart if not" checks.
- GET /health/ready    Readiness: is the app able to serve real traffic?
                       Checks Firebase connectivity when Firebase is
                       configured. Returns 503 if a configured dependency
                       is unreachable. Use this for "route traffic here"
                       checks / load balancer health checks.
"""
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.core.firebase import FirebaseState, get_firebase_state

router = APIRouter(tags=["health"])
logger = logging.getLogger("app.health")

_started_at = time.monotonic()


@router.get("/health")
def liveness(settings: Settings = Depends(get_settings)) -> dict:
    """Liveness check: confirm the process is running and able to respond."""
    return {
        "status": "ok",
        "service": "krishka-vachana-backend",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.monotonic() - _started_at, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    firebase: FirebaseState = Depends(get_firebase_state),
) -> dict:
    """Readiness check: verify dependencies are available and the service can handle traffic."""
    checks = {}

    if firebase.is_configured:
        try:
            client = firebase.firestore_client()
            # Cheap connectivity probe - list a single doc, don't care if
            # the collection is empty, only that the call doesn't raise.
            next(iter(client.collection("_health_check").limit(1).stream()), None)
            checks["firestore"] = "ok"
        except Exception:  # pragma: no cover - depends on live infra
            logger.exception("Firestore readiness check failed")
            checks["firestore"] = "error"
    else:
        if settings.is_development and settings.allow_dev_auth_fallback:
            checks["firestore"] = "not_configured (using in-memory fallback)"
        else:
            checks["firestore"] = "not_configured"

    healthy = checks["firestore"] in {"ok", "not_configured (using in-memory fallback)"}
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if healthy else "degraded", "checks": checks}
