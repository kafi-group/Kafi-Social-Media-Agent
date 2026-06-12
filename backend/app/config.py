"""
Application Configuration Management
Uses Pydantic Settings for environment variables
"""

import logging
import secrets
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode

logger = logging.getLogger(__name__)

# Local dev fallback when INTERNAL_API_KEY is not in .env (gitignored).
_INTERNAL_API_KEY_FILE = Path(__file__).resolve().parent.parent / ".internal_api_key"


def _bootstrap_internal_api_key(settings: "Settings") -> None:
    """
    In development, provision a stable INTERNAL_API_KEY when .env leaves it blank.
    Production/staging must set INTERNAL_API_KEY explicitly in the environment.
    """
    if settings.INTERNAL_API_KEY or settings.ENVIRONMENT == "production":
        return

    if _INTERNAL_API_KEY_FILE.exists():
        stored = _INTERNAL_API_KEY_FILE.read_text(encoding="utf-8").strip()
        if stored:
            settings.INTERNAL_API_KEY = stored
            logger.info(
                "INTERNAL_API_KEY loaded from %s (development)",
                _INTERNAL_API_KEY_FILE.name,
            )
            return

    generated = secrets.token_urlsafe(40)
    _INTERNAL_API_KEY_FILE.write_text(generated, encoding="utf-8")
    settings.INTERNAL_API_KEY = generated
    logger.info(
        "INTERNAL_API_KEY auto-generated for development and saved to %s",
        _INTERNAL_API_KEY_FILE.name,
    )


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # App Settings
    APP_NAME: str = "Kafi Social Agent"
    API_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # Database Settings
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/kafi_social_agent"
    DATABASE_ECHO: bool = False  # Set to True to log SQL queries

    # Supabase Settings (Optional)
    SUPABASE_URL: str = ""
    SUPABASE_API_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""

    # LLM Provider Settings
    # Using Google Gemini API (fast, free, no local model needed)
    LLM_PROVIDER: str = "gemini"

    # Ollama Settings (used when LLM_PROVIDER="ollama")
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_TIMEOUT: int = 300

    # Google Gemini Settings (used when LLM_PROVIDER="gemini")
    # Get a free API key at https://aistudio.google.com/apikey
    GEMINI_API_KEY: str = ""
    # Primary model. gemini-3.5-flash can hit 503 under high demand; fallback is used automatically.
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_TIMEOUT: int = 120
    GEMINI_MAX_RETRIES: int = 3

    # LLM Settings
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2048
    TOP_P: float = 0.9

    # Content Creation chatbot — separate Gemini key (does NOT use GEMINI_API_KEY)
    # Get a 2nd free key at https://aistudio.google.com/apikey (same steps as your posting key)
    CREATION_GEMINI_API_KEY: str = ""
    CREATION_GEMINI_MODEL: str = "gemini-2.5-flash"
    CREATION_GEMINI_FALLBACK_MODEL: str = "gemini-2.0-flash"

    # Content Creation - Gemini web app deep link (image/video are created in Gemini)
    GEMINI_WEB_URL: str = "https://gemini.google.com/app"

    # Scraper Settings
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_BATCH_SIZE: int = 10
    SCRAPER_SCHEDULE_INTERVAL: int = 3600  # seconds

    # Rival Review Settings
    # YouTube Data API v3 key for PUBLIC competitor channel stats (separate from
    # the YouTube upload OAuth creds). Get a free key in Google Cloud Console.
    YOUTUBE_DATA_API_KEY: str = ""
    # When True, a background job refreshes rival snapshots on SCRAPER_SCHEDULE_INTERVAL.
    RIVAL_AUTO_REFRESH: bool = False

    # Post Scheduler Settings (auto-publish scheduled calendar events)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_POLL_INTERVAL_SECONDS: int = 30  # how often to check for due posts

    # Redis (optional caching)
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_ENABLED: bool = False

    # CORS Settings (comma-separated in .env, e.g. http://localhost:3000,http://127.0.0.1:3000)
    CORS_ORIGINS: Annotated[
        list[str],
        NoDecode,
    ] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # JWT/Auth Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Security Settings ─────────────────────────────────────────────────────
    # Internal API key that must be sent in the X-Internal-API-Key header to
    # access destructive endpoints (e.g. DELETE /content/clear-all).
    # In development, if blank, a key is auto-generated and saved to
    # backend/.internal_api_key on first startup. Set explicitly in production.
    INTERNAL_API_KEY: str = ""

    # Approval email magic-link expiry (hours). Links older than this are rejected.
    APPROVAL_TOKEN_EXPIRE_HOURS: int = 48

    # PIN brute-force protection: lock out an IP after this many failed attempts …
    PIN_MAX_ATTEMPTS: int = 5
    # … for this many minutes.
    PIN_LOCKOUT_MINUTES: int = 15

    # Maximum request body size in megabytes (enforced by middleware)
    MAX_REQUEST_BODY_MB: int = 20

    # Social Media API Settings
    LINKEDIN_ACCESS_TOKEN: str = ""
    LINKEDIN_PERSON_ID: str = ""
    LINKEDIN_ACCOUNT_1_LABEL: str = "Account 1"
    LINKEDIN_ACCOUNT_1_ACCESS_TOKEN: str = ""
    LINKEDIN_ACCOUNT_1_PERSON_ID: str = ""
    LINKEDIN_ACCOUNT_2_LABEL: str = "Account 2"
    LINKEDIN_ACCOUNT_2_ACCESS_TOKEN: str = ""
    LINKEDIN_ACCOUNT_2_PERSON_ID: str = ""
    LINKEDIN_ACCOUNT_3_LABEL: str = "Account 3"
    LINKEDIN_ACCOUNT_3_ACCESS_TOKEN: str = ""
    LINKEDIN_ACCOUNT_3_PERSON_ID: str = ""
    LINKEDIN_ORGANIZATION_ID: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_PAGE_ID: str = ""
    FACEBOOK_PAGE_ACCESS_TOKEN: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/meta/callback"
    INSTAGRAM_ACCOUNT_ID: str = ""
    META_GRAPH_API_VERSION: str = "v21.0"

    # YouTube Settings (YouTube Data API v3 - OAuth 2.0)
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/youtube/callback"
    YOUTUBE_CHANNEL_ID: str = ""
    YOUTUBE_VIDEO_CATEGORY_ID: str = "22"  # 22 = People & Blogs (default)
    # Scopes required for upload + analytics (comma-separated in .env)
    YOUTUBE_OAUTH_SCOPES: str = (
        "https://www.googleapis.com/auth/youtube.upload,"
        "https://www.googleapis.com/auth/youtube.readonly,"
        "https://www.googleapis.com/auth/yt-analytics.readonly"
    )

    # Draft / Test Mode
    DRAFT_MODE: bool = True

    # Supabase Storage Settings
    SUPABASE_STORAGE_BUCKET: str = "Media"

    # Upload Settings
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # Designer Approval Workflow
    # When True, non-designers must get a post approved by the designer before it
    # publishes. Designers prove identity with DESIGNER_PIN to post directly.
    APPROVAL_REQUIRED: bool = True
    DESIGNER_PIN: str = ""  # shared secret; empty disables direct posting
    DESIGNER_EMAIL: str = ""  # where approval-request emails are sent
    # Public base URL of the backend, used to build media URLs and the
    # approve/reject links inside approval emails.
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    # SMTP (Gmail) settings for approval emails
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""  # Gmail App Password (not your normal password)
    SMTP_FROM: str = ""  # defaults to SMTP_USERNAME when empty
    SMTP_USE_TLS: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore unknown env vars so .env can have extra vars


settings = Settings()
_bootstrap_internal_api_key(settings)
