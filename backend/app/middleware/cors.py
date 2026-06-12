"""
CORS Middleware Configuration

Origins are read from CORS_ORIGINS in .env so production deployments can
restrict access without touching code.

Methods and headers are restricted to the minimum required — wildcard
allow_methods / allow_headers are intentionally NOT used.
"""

from app.config import settings


def get_cors_settings() -> dict:
    """Return CORS settings driven by the environment configuration."""
    return {
        "allow_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        # Explicit list prevents accidental exposure of exotic HTTP verbs
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # Only the headers the frontend actually sends
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-Internal-API-Key",
            "Accept",
            "Origin",
            "X-Requested-With",
        ],
        "expose_headers": ["X-Request-ID"],
        "max_age": 600,  # pre-flight cache: 10 minutes
    }
