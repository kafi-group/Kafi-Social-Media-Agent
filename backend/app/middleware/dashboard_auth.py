"""Require a valid dashboard JWT on protected API routes."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.services import auth_service

# Paths that stay public (OAuth callbacks, health).
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/youtube",
    "/api/v1/auth/linkedin",
    "/api/v1/auth/meta",
)


def _is_public_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


def _extract_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


async def dashboard_auth_middleware(request: Request, call_next):
    if not auth_service.credentials_configured():
        return await call_next(request)

    if request.method == "OPTIONS" or _is_public_path(request.url.path):
        return await call_next(request)

    token = _extract_bearer_token(request)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated. Log in to access the dashboard."},
        )

    payload = auth_service.decode_access_token(token)
    if not payload or not payload.get("sub"):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired session. Please log in again."},
        )

    request.state.dashboard_user = payload["sub"]
    return await call_next(request)
