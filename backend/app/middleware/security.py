"""
Security Headers Middleware

Attaches defensive HTTP headers to every response:
  - X-Content-Type-Options   : prevents MIME-sniffing attacks
  - X-Frame-Options           : blocks clickjacking (DENY)
  - X-XSS-Protection          : triggers browser XSS filter
  - Referrer-Policy           : limits referrer leakage
  - Permissions-Policy        : disables sensitive browser APIs
  - Strict-Transport-Security : forces HTTPS (production only)
  - Cache-Control             : prevents caching of API responses
  - Server header removal     : hides server fingerprint
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every outgoing response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Strip fingerprinting headers that uvicorn/starlette may add.
        # MutableHeaders has no .pop(); use del with a case-insensitive check.
        for header in ("server", "x-powered-by"):
            if header in response.headers:
                del response.headers[header]

        return response
