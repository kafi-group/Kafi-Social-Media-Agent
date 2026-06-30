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
    # full = entire platform; creation-only = Prompt Studio (/creation) API surface only
    APP_MODE: Literal["full", "creation-only"] = "full"
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
    # Fail fast when the DB host is unreachable (seconds). Lower in dev avoids long UI spinners.
    DATABASE_CONNECT_TIMEOUT: int = 5

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
    # Optional extra keys (comma-separated). Tried in order when quota/rate limits hit.
    # Use keys from different Google accounts for separate free-tier quotas.
    CREATION_GEMINI_API_KEYS: str = ""
    CREATION_GEMINI_MODEL: str = "gemini-2.5-flash"
    CREATION_GEMINI_FALLBACK_MODEL: str = "gemini-2.0-flash"
    # Optional full model chain (comma-separated). When empty, primary + fallback above are used.
    CREATION_GEMINI_MODELS: str = ""

    # Content Creation — image generation
    # IMAGE_PROVIDER: gemini | modelslab | cloudflare (Workers AI, free tier)
    IMAGE_PROVIDER: Literal["gemini", "modelslab", "cloudflare"] = "gemini"
    # Gemini — separate Google account / API key recommended
    IMAGE_GEMINI_API_KEY: str = ""
    IMAGE_GEMINI_MODEL: str = "gemini-2.5-flash-image"
    IMAGE_GEMINI_FALLBACK_MODEL: str = "gemini-3.1-flash-image-preview"
    IMAGE_GEMINI_TIMEOUT: int = 180
    # ModelsLab — https://modelslab.com (free tier ~100 calls/day, no card)
    MODELSLAB_API_KEY: str = ""
    MODELSLAB_IMAGE_MODEL: str = "hidream-o1"
    MODELSLAB_IMAGE_WIDTH: int = 1024
    MODELSLAB_IMAGE_HEIGHT: int = 1024
    MODELSLAB_INFERENCE_STEPS: int = 31
    MODELSLAB_GUIDANCE_SCALE: float = 7.5
    MODELSLAB_CLIP_SKIP: int = 2
    MODELSLAB_NEGATIVE_PROMPT: str = (
        "blurry, low quality, distorted, deformed, watermark, ugly, bad anatomy"
    )
    MODELSLAB_IMAGE_TIMEOUT: int = 180

    # Cloudflare Workers AI — https://developers.cloudflare.com/workers-ai/
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_IMAGE_MODEL: str = "@cf/black-forest-labs/flux-1-schnell"
    CLOUDFLARE_IMAGE_STEPS: int = 4
    CLOUDFLARE_IMAGE_TIMEOUT: int = 120

    # Content Creation - Gemini web app deep link (optional fallback for manual edits)
    GEMINI_WEB_URL: str = "https://gemini.google.com/app"
    # Meta AI — where the team pastes generated image/video prompts
    META_AI_WEB_URL: str = "https://www.meta.ai/"
    # ElevenLabs — text-to-speech for video voice-overs
    ELEVENLABS_WEB_URL: str = "https://elevenlabs.io/app/speech-synthesis/text-to-speech"
    # Google Flow — character creation for video projects
    GOOGLE_FLOW_CHARACTERS_URL: str = (
        "https://labs.google/fx/tools/flow/project/cc16a3ce-33ec-4248-bb1a-3341c7817479/characters"
    )
    GOOGLE_FLOW_FINAL_PRODUCT_URL: str = (
        "https://labs.google/fx/tools/flow/project/0b5aa7ed-bd40-490d-af9a-24208f855710"
    )

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
            raw = value.strip()
            if raw.startswith("CORS_ORIGINS="):
                raw = raw.split("=", 1)[1].strip()
            origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        else:
            origins = value
        cleaned: list[str] = []
        for origin in origins:
            o = origin.strip()
            if o.startswith("CORS_ORIGINS="):
                o = o.split("=", 1)[1].strip()
            if o:
                cleaned.append(o)
        return cleaned

    # Allow any Vercel preview/production URL (*.vercel.app). Preview deploys get a
    # unique subdomain per build, so a fixed CORS_ORIGINS list cannot cover them all.
    CORS_ALLOW_VERCEL_REGEX: bool = True
    CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Use psycopg v3 driver (requirements.txt) for plain postgresql:// URLs."""
        url = value.strip()
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    # JWT/Auth Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours — dashboard session length
    # Dashboard login (required to access API + frontend /dashboard)
    DASHBOARD_USERNAME: str = ""
    DASHBOARD_PASSWORD: str = ""

    # ── Security Settings ─────────────────────────────────────────────────────
    # Internal API key that must be sent in the X-Internal-API-Key header to
    # access destructive endpoints (e.g. DELETE /content/clear-all).
    # In development, if blank, a key is auto-generated and saved to
    # backend/.internal_api_key on first startup. Set explicitly in production.
    INTERNAL_API_KEY: str = ""

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
    # Dedicated token for company-page analytics (rw_organization_admin scope).
    # Obtain via /api/v1/auth/linkedin — separate from personal posting tokens.
    LINKEDIN_ORGANIZATION_ACCESS_TOKEN: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/linkedin/callback"
    LINKEDIN_OAUTH_SCOPES: str = (
        # Analytics only — do not add w_organization_social unless LinkedIn approved it
        # for your app under Marketing Developer Platform.
        "openid profile email rw_organization_admin"
    )
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
    # YouTube upload visibility: private | unlisted | public
    YOUTUBE_DEFAULT_PRIVACY_STATUS: str = "public"
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

    # Designer Approval Workflow (QA Checker)
    # When True, non-designers must get a post approved by the designer before it
    # publishes. Designers prove identity with DESIGNER_PIN to post directly.
    APPROVAL_REQUIRED: bool = True
    DESIGNER_PIN: str = ""  # shared secret; empty disables direct posting

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore unknown env vars so .env can have extra vars


settings = Settings()
_bootstrap_internal_api_key(settings)


def _parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def get_creation_gemini_api_keys() -> list[str]:
    """API keys for the creation chatbot, in failover order."""
    keys: list[str] = []
    primary = settings.CREATION_GEMINI_API_KEY.strip()
    if primary:
        keys.append(primary)
    for key in _parse_csv(settings.CREATION_GEMINI_API_KEYS):
        if key not in keys:
            keys.append(key)
    return keys


def get_creation_gemini_models() -> list[str]:
    """Gemini models for the creation chatbot, in failover order."""
    models = _parse_csv(settings.CREATION_GEMINI_MODELS)
    if models:
        return models

    ordered: list[str] = []
    for model in (settings.CREATION_GEMINI_MODEL, settings.CREATION_GEMINI_FALLBACK_MODEL):
        name = model.strip()
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def get_image_gemini_api_key() -> str:
    """Dedicated API key for Prompt Studio image generation."""
    return settings.IMAGE_GEMINI_API_KEY.strip()


def get_image_gemini_models() -> list[str]:
    """Gemini image models, in failover order."""
    ordered: list[str] = []
    for model in (settings.IMAGE_GEMINI_MODEL, settings.IMAGE_GEMINI_FALLBACK_MODEL):
        name = model.strip()
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def is_image_generation_ready() -> bool:
    """True when the configured IMAGE_PROVIDER has credentials."""
    provider = (settings.IMAGE_PROVIDER or "gemini").strip().lower()
    if provider == "modelslab":
        return bool(settings.MODELSLAB_API_KEY.strip())
    if provider == "gemini":
        return bool(get_image_gemini_api_key())
    if provider == "cloudflare":
        return bool(
            settings.CLOUDFLARE_ACCOUNT_ID.strip()
            and settings.CLOUDFLARE_API_TOKEN.strip()
        )
    return False


def get_image_generation_model_label() -> str:
    """Human-readable label for the active image provider/model."""
    provider = (settings.IMAGE_PROVIDER or "gemini").strip().lower()
    if provider == "modelslab":
        model = settings.MODELSLAB_IMAGE_MODEL.strip() or "hidream-o1"
        return f"ModelsLab {model}"
    if provider == "cloudflare":
        model = settings.CLOUDFLARE_IMAGE_MODEL.strip() or "@cf/black-forest-labs/flux-1-schnell"
        short = model.split("/")[-1] if "/" in model else model
        return f"Cloudflare {short}"
    model = settings.IMAGE_GEMINI_MODEL.strip() or "gemini"
    return model.replace("gemini-", "Gemini ").replace("-", " ").title()
