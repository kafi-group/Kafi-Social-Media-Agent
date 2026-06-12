"""
Global Exception Handlers

Rules:
 - Application-level exceptions (KafiAgentException) → 400 with safe message.
 - Pydantic validation errors (422) → in development return field details;
   in production return a generic message so schema details aren't leaked.
 - Unhandled exceptions → 500 with no internal detail exposed to callers.
   Full tracebacks are always logged server-side.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.exceptions import KafiAgentException

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(KafiAgentException)
    async def kafi_exception_handler(request: Request, exc: KafiAgentException):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Return 422 with field-level errors in dev; generic message in production."""
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        if settings.ENVIRONMENT == "production":
            return JSONResponse(
                status_code=422,
                content={"detail": "Request validation failed. Check the submitted data."},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}"
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please try again later."},
        )
