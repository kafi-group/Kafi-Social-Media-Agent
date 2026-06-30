"""
FastAPI Application Entry Point
Kafi Commodities Social Media & Branding AI Agent System
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware.cors import get_cors_settings
from app.middleware.error_handler import setup_exception_handlers
from app.middleware.rate_limiter import limiter
from app.middleware.dashboard_auth import dashboard_auth_middleware
from app.middleware.security import SecurityHeadersMiddleware
from app.routes import (
    health, content, calendar, analytics, qa,
    scraper, rival, youtube_auth, meta_auth, linkedin_auth, social, creation, approval, auth,
)
from app.services import auth_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info(f"Starting Kafi Social Agent - Environment: {settings.ENVIRONMENT}")
    logger.info(f"APP_MODE: {settings.APP_MODE}")
    logger.info(f"API Version: {settings.API_VERSION}")
    if settings.APP_MODE == "full":
        logger.info(f"LLM Provider: Google Gemini ({settings.GEMINI_MODEL})")

    if settings.ENVIRONMENT != "production":
        logger.info(f"API Docs: http://localhost:{settings.PORT}/docs")
    else:
        logger.info("API Docs: disabled in production")

    if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
        logger.info(f"Storage Backend: Supabase (bucket: {settings.SUPABASE_STORAGE_BUCKET})")
    else:
        logger.info("Storage Backend: Local Disk (backend/uploads/)")

    if not settings.INTERNAL_API_KEY:
        logger.warning(
            "INTERNAL_API_KEY is not set — the DELETE /content/clear-all endpoint "
            "is disabled until it is configured in .env (required in production)."
        )
    elif settings.ENVIRONMENT != "production":
        logger.info("Destructive admin endpoints enabled (INTERNAL_API_KEY configured).")

    if auth_service.credentials_configured():
        logger.info("Dashboard login enabled (DASHBOARD_USERNAME configured).")
    else:
        logger.warning(
            "DASHBOARD_USERNAME / DASHBOARD_PASSWORD not set — "
            "API routes are open until dashboard login is configured."
        )

    if settings.APP_MODE == "full":
        from app.services.scheduler import start_scheduler
        start_scheduler()
    else:
        logger.info("APP_MODE=creation-only — post scheduler disabled")

    yield

    if settings.APP_MODE == "full":
        from app.services.scheduler import shutdown_scheduler
        shutdown_scheduler()
    logger.info("Shutting down Kafi Social Agent")


# ── Conditionally expose OpenAPI docs ────────────────────────────────────────
# In production, /docs and /redoc are disabled to reduce attack surface.
_is_production = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="Kafi Commodities Social Media & Branding AI Agent",
    description="Specialized AI agent system for B2B/B2C social media strategy, content generation, and optimization",
    version=settings.API_VERSION,
    lifespan=lifespan,
    # Disable interactive docs in production
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# ── Rate limiter state ────────────────────────────────────────────────────────
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again later."},
        headers={"Retry-After": "60"},
    )


# ── Middleware (added in reverse order — last added = outermost) ──────────────

# 1. Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# 2. Request body size limit (must sit inside CORS so 413 responses get CORS headers)
_MAX_BODY_BYTES = settings.MAX_REQUEST_BODY_MB * 1024 * 1024


@app.middleware("http")
async def require_dashboard_auth(request: Request, call_next):
    return await dashboard_auth_middleware(request, call_next)


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body exceeds the {settings.MAX_REQUEST_BODY_MB} MB limit."
                        )
                    },
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header."},
            )
    return await call_next(request)

# 3. CORS (outermost — wraps all responses, including 413/400 from body-size guard)
cors_settings = get_cors_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings["allow_origins"],
    allow_origin_regex=cors_settings.get("allow_origin_regex"),
    allow_credentials=cors_settings["allow_credentials"],
    allow_methods=cors_settings["allow_methods"],
    allow_headers=cors_settings["allow_headers"],
    expose_headers=cors_settings.get("expose_headers", []),
    max_age=cors_settings.get("max_age", 600),
)


# ── Exception handlers ────────────────────────────────────────────────────────
setup_exception_handlers(app)

# ── Static file serving ───────────────────────────────────────────────────────
uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# ── Route modules ─────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/api/v1", tags=["Auth"])
app.include_router(health.router,   prefix="/api/v1", tags=["Health"])
app.include_router(creation.router, prefix="/api/v1", tags=["Content Creation"])
app.include_router(youtube_auth.router, prefix="/api/v1", tags=["YouTube Auth"])
app.include_router(linkedin_auth.router, prefix="/api/v1", tags=["LinkedIn Auth"])
app.include_router(meta_auth.router,    prefix="/api/v1", tags=["Meta Auth"])

if settings.APP_MODE == "full":
    app.include_router(content.router,      prefix="/api/v1", tags=["Content"])
    app.include_router(calendar.router,     prefix="/api/v1", tags=["Calendar"])
    app.include_router(analytics.router,    prefix="/api/v1", tags=["Analytics"])
    app.include_router(qa.router,           prefix="/api/v1", tags=["QA"])
    app.include_router(approval.router,     prefix="/api/v1", tags=["Approvals"])
    app.include_router(scraper.router,      prefix="/api/v1", tags=["Scraper"])
    app.include_router(rival.router,        prefix="/api/v1", tags=["Rival Review"])
    app.include_router(social.router,       prefix="/api/v1", tags=["Social"])


@app.get("/")
async def root():
    """Root endpoint — minimal info exposed in production."""
    return {
        "status": "success",
        "message": "Kafi Commodities Social Media & Branding AI Agent API",
        "api_version": settings.API_VERSION,
        "app_mode": settings.APP_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
