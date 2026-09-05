"""Shared application exceptions and their FastAPI handlers.

Keeping this in one place means every endpoint returns errors in the same
shape, which is what the frontend team needs for consistent error-state UI
(see UI_rules.md section 22, "Error States").
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.exceptions")


class AppError(Exception):
    """Base class for expected, handled application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "app_error"

    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class NotFoundError(AppError):
    """Exception for resource not found errors (404)."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ConflictError(AppError):
    """Exception for resource conflict errors (409)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class ValidationAppError(AppError):
    """Exception for validation errors (422)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_error"


class UnauthorizedError(AppError):
    """Exception for authentication/authorization errors (401)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ForbiddenError(AppError):
    """Exception for authenticated callers lacking permission (403)."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class ServiceUnavailableError(AppError):
    """Exception for unavailable required infrastructure (503)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "service_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers for the FastAPI application."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        """Handle AppError exceptions and return consistent error responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.error_code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI request validation errors and return consistent error responses."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        """Safety net for any exception not raised as an AppError.

        Every call site that can reach an external dependency (Firestore,
        Secret Manager, the SMS/congestion/payment-gateway HTTP clients)
        already has its own try/except that translates failures into an
        AppError subclass. This handler exists so a *future* call site that
        forgets to do that still returns the same JSON error shape instead
        of a bare, unshaped 500 - the internals are logged server-side only,
        never included in the response.
        """
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred"}},
        )
