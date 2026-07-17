"""
Persistent OAuth credential store for social analytics / publishing.

Tokens are written to (in order of durability):
1. Runtime settings (immediate effect — no restart)
2. PostgreSQL platform_credential table (survives Railway redeploys)
3. Local backend/.env and backend/.oauth_tokens.json (local / volume persistence)

On startup, DB + JSON values are loaded into settings so analytics keep working
without manually re-pasting tokens after every expiry or deploy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from app.config import settings
from app.utils.logger import logger

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BACKEND_DIR / ".env"
JSON_PATH = BACKEND_DIR / ".oauth_tokens.json"

# Keys this store is allowed to persist (never write unrelated secrets).
MANAGED_KEYS = frozenset(
    {
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "FACEBOOK_USER_ACCESS_TOKEN",
        "FACEBOOK_PAGE_ID",
        "INSTAGRAM_ACCOUNT_ID",
        "YOUTUBE_REFRESH_TOKEN",
        "YOUTUBE_CHANNEL_ID",
    }
)


def _quote_env_value(value: str) -> str:
    if re.search(r'[\s#"\'\\]', value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _upsert_env_file(updates: dict[str, str]) -> None:
    """Create or update key=value pairs in backend/.env."""
    if not updates:
        return

    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={_quote_env_value(remaining.pop(key))}")
        else:
            new_lines.append(line)

    if remaining:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# Auto-saved by OAuth token store — do not commit")
        for key, value in remaining.items():
            new_lines.append(f"{key}={_quote_env_value(value)}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _upsert_json_file(updates: dict[str, str]) -> None:
    data: dict[str, str] = {}
    if JSON_PATH.exists():
        try:
            loaded = json.loads(JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = {str(k): str(v) for k, v in loaded.items() if k in MANAGED_KEYS}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Could not read {JSON_PATH.name}: {exc}")

    data.update(updates)
    JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _apply_runtime(updates: dict[str, str]) -> None:
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


def _upsert_database(updates: dict[str, str]) -> None:
    from datetime import datetime

    from app.database.db import SessionLocal
    from app.database.models import PlatformCredential

    db = SessionLocal()
    try:
        for key, value in updates.items():
            row = (
                db.query(PlatformCredential)
                .filter(PlatformCredential.key == key)
                .first()
            )
            if row:
                row.value = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(
                    PlatformCredential(
                        key=key,
                        value=value,
                        updated_at=datetime.utcnow(),
                    )
                )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(f"Could not persist OAuth tokens to database: {exc}")
    finally:
        db.close()


def _load_database() -> dict[str, str]:
    from app.database.db import SessionLocal
    from app.database.models import PlatformCredential

    db = SessionLocal()
    try:
        rows = db.query(PlatformCredential).all()
        return {
            row.key: row.value
            for row in rows
            if row.key in MANAGED_KEYS and (row.value or "").strip()
        }
    except Exception as exc:
        logger.warning(f"Could not load OAuth tokens from database: {exc}")
        return {}
    finally:
        db.close()


def _load_json_file() -> dict[str, str]:
    if not JSON_PATH.exists():
        return {}
    try:
        loaded = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return {}
        return {
            str(k): str(v)
            for k, v in loaded.items()
            if k in MANAGED_KEYS and str(v).strip()
        }
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Could not load {JSON_PATH.name}: {exc}")
        return {}


def save_credentials(updates: dict[str, str]) -> list[str]:
    """
    Persist credential updates everywhere. Returns the keys that were saved.
    Empty / whitespace values are ignored.
    """
    cleaned = {
        key: value.strip()
        for key, value in updates.items()
        if key in MANAGED_KEYS and isinstance(value, str) and value.strip()
    }
    if not cleaned:
        return []

    _apply_runtime(cleaned)
    try:
        _upsert_env_file(cleaned)
    except OSError as exc:
        logger.warning(f"Could not update .env with OAuth tokens: {exc}")
    try:
        _upsert_json_file(cleaned)
    except OSError as exc:
        logger.warning(f"Could not update {JSON_PATH.name}: {exc}")
    _upsert_database(cleaned)

    logger.info(f"Persisted OAuth credentials: {', '.join(sorted(cleaned))}")
    return list(cleaned.keys())


def load_persisted_credentials() -> list[str]:
    """
    Load stored credentials into runtime settings on startup.
    DB wins over JSON; env/settings already loaded by pydantic are only
    overwritten when the persisted value is non-empty.
    """
    merged: dict[str, str] = {}
    merged.update(_load_json_file())
    merged.update(_load_database())

    applied: list[str] = []
    for key, value in merged.items():
        if not hasattr(settings, key):
            continue
        current = getattr(settings, key) or ""
        # Prefer persisted store when present — keeps Railway redeploys in sync
        # with the last successful OAuth / auto-refresh.
        if value and value != current:
            setattr(settings, key, value)
            applied.append(key)
        elif value and not current:
            setattr(settings, key, value)
            applied.append(key)

    if applied:
        logger.info(f"Loaded persisted OAuth credentials: {', '.join(sorted(applied))}")
    return applied


def ensure_credentials_table() -> bool:
    """Create platform_credential table if missing. Returns True when ready."""
    try:
        from sqlalchemy import inspect

        from app.database.db import engine
        from app.database.models import PlatformCredential

        inspector = inspect(engine)
        if "platform_credential" not in set(inspector.get_table_names()):
            PlatformCredential.__table__.create(bind=engine)
            logger.info("Created platform_credential table")
        return True
    except Exception as exc:
        logger.warning(f"platform_credential table unavailable: {exc}")
        return False


def credential_status(keys: Iterable[str] | None = None) -> dict[str, bool]:
    """Return whether each managed key is set in runtime settings."""
    check = list(keys) if keys is not None else sorted(MANAGED_KEYS)
    return {
        key: bool((getattr(settings, key, "") or "").strip())
        for key in check
        if key in MANAGED_KEYS
    }
