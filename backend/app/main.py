from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title="Krishka Vachana API",
    description="Backend API for Krishka Vachana - SIH26032",
    version=settings.app_version,
    # Default /docs is disabled here; a re-skinned version is served by
    # app.api.docs below. Both /docs and /redoc can be fully switched off in
    # production via ENABLE_DOCS=false.
    docs_url=None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.api_v1_prefix)

if settings.enable_docs:
    from app.api.docs import router as docs_router

    app.include_router(docs_router)


@app.get("/")
def root() -> dict:
    """Return basic API information and links to documentation and health endpoints."""
    return {
        "name": "Krishka Vachana API",
        "version": settings.app_version,
        "docs": "/docs" if settings.enable_docs else None,
        "status": "/status" if settings.enable_docs else None,
        "health": f"{settings.api_v1_prefix}/health",
    }
