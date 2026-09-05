"""Custom docs (/docs) and status (/status) pages.

FastAPI's default docs_url/redoc_url still work out of the box, but we
override /docs with a lightly re-skinned Swagger UI (brand colors from
UI_rules.md) and add a plain-English /status page for humans, on top of
the machine-readable JSON at /api/v1/health and /api/v1/health/ready.
"""
from fastapi import APIRouter, Depends
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.core.branding import BRAND, page_shell
from app.core.config import Settings, get_settings
from app.core.firebase import FirebaseState, get_firebase_state

router = APIRouter(include_in_schema=False)

_SWAGGER_BRAND_CSS = f"""
<style>
  .topbar {{ background-color: {BRAND['primary_dark']} !important; }}
  .swagger-ui .btn.authorize {{ border-color: {BRAND['primary_button']}; color: {BRAND['primary_button']}; }}
  .swagger-ui .btn.authorize svg {{ fill: {BRAND['primary_button']}; }}
  .swagger-ui .opblock.opblock-post {{ border-color: {BRAND['primary_button']}; background: {BRAND['primary_light']}; }}
  .swagger-ui .opblock.opblock-post .opblock-summary-method {{ background: {BRAND['primary_button']}; }}
</style>
"""


@router.get("/docs", response_class=HTMLResponse)
def custom_swagger_docs() -> HTMLResponse:
    """Serve custom-branded Swagger UI documentation."""
    response = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Krishka Vachana API - Docs",
    )
    html = response.body.decode("utf-8").replace("</head>", f"{_SWAGGER_BRAND_CSS}</head>")
    return HTMLResponse(html)


@router.get("/status", response_class=HTMLResponse)
def status_page(
    settings: Settings = Depends(get_settings),
    firebase: FirebaseState = Depends(get_firebase_state),
) -> HTMLResponse:
    """Serve a human-readable status page showing service health and configuration."""
    if firebase.is_configured:
        firebase_badge = '<span class="badge badge-ok">configured</span>'
    elif settings.is_development and settings.allow_dev_auth_fallback:
        firebase_badge = '<span class="badge badge-warn">using in-memory fallback</span>'
    else:
        firebase_badge = '<span class="badge badge-warn">not configured</span>'
    if settings.congestion_prediction_api_url:
        congestion_badge = '<span class="badge badge-ok">configured</span>'
    else:
        congestion_badge = '<span class="badge badge-warn">using heuristic fallback</span>'
    version = settings.app_version
    environment = settings.environment
    api_prefix = settings.api_v1_prefix
    body = f"""
      <div class="card">
        <h2 style="margin-top:0;">Service status</h2>
        <table>
          <tr><th>Status</th><td><span class="badge badge-ok">running</span></td></tr>
          <tr><th>Version</th><td><code>{version}</code></td></tr>
          <tr><th>Environment</th><td><code>{environment}</code></td></tr>
          <tr><th>Firebase</th><td>{firebase_badge}</td></tr>
          <tr><th>Congestion prediction (AI/ML)</th><td>{congestion_badge}</td></tr>
        </table>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">Links</h2>
        <p><a class="link" href="/docs">Interactive API docs (Swagger)</a></p>
        <p><a class="link" href="/redoc">API reference (ReDoc)</a></p>
        <p><a class="link" href="{api_prefix}/health">Liveness check (JSON)</a></p>
        <p><a class="link" href="{api_prefix}/health/ready">Readiness check (JSON)</a></p>
      </div>
    """
    return HTMLResponse(page_shell("Krishka Vachana API - Status", body))
