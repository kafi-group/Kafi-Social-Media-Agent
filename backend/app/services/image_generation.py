"""
Prompt Studio image generation — routes by IMAGE_PROVIDER (gemini, modelslab, cloudflare).

Gemini-first policy:
  - Prefer Gemini for the first IMAGE_GEMINI_PRIORITY_COUNT successful images each day
  - After that daily Gemini budget, use Cloudflare Flux
  - If Gemini hits quota/billing before the budget is used, fall back to Cloudflare
    so the user still gets an image (and the UI labels the provider clearly)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.config import _cloudflare_image_ready, settings, resolve_image_provider
from app.services.cloudflare_image import generate_cloudflare_image
from app.services.gemini_image import extract_image_prompt, generate_image as generate_gemini_image
from app.services.modelslab_image import generate_modelslab_image
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger

_GEMINI_DAILY_COUNTER_PATH = Path(__file__).resolve().parent.parent / ".gemini_image_daily.json"


def _is_gemini_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        term in text
        for term in ("quota", "billing", "rate limit", "resource_exhausted", "429")
    )


def _is_gemini_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        term in text
        for term in (
            "401",
            "403",
            "unauthenticated",
            "invalid authentication",
            "not authorized",
            "invalid or not authorized",
        )
    )


def _gemini_priority_limit() -> int:
    try:
        return max(0, int(settings.IMAGE_GEMINI_PRIORITY_COUNT))
    except (TypeError, ValueError):
        return 5


def _read_gemini_daily_count() -> tuple[str, int]:
    today = date.today().isoformat()
    try:
        if _GEMINI_DAILY_COUNTER_PATH.exists():
            data = json.loads(_GEMINI_DAILY_COUNTER_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("date") == today:
                return today, max(0, int(data.get("success_count", 0)))
    except Exception as exc:
        logger.warning(f"Could not read Gemini daily image counter: {exc}")
    return today, 0


def _write_gemini_daily_count(day: str, count: int) -> None:
    try:
        _GEMINI_DAILY_COUNTER_PATH.write_text(
            json.dumps({"date": day, "success_count": max(0, int(count))}),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(f"Could not write Gemini daily image counter: {exc}")


def _increment_gemini_daily_count() -> int:
    day, count = _read_gemini_daily_count()
    count += 1
    _write_gemini_daily_count(day, count)
    return count


def _cloudflare_result(prompt: str, *, reason: str) -> dict:
    result = generate_cloudflare_image(prompt)
    result["provider"] = "cloudflare"
    model = result.get("model", "@cf/black-forest-labs/flux-1-schnell")
    if reason == "daily_budget":
        result["model"] = f"{model} (after Gemini daily budget)"
        result["fallback_reason"] = (
            f"Gemini daily priority budget used "
            f"({_gemini_priority_limit()} images). Using Cloudflare Flux."
        )
    elif reason == "quota":
        result["model"] = f"{model} (Gemini quota fallback)"
        result["fallback_reason"] = (
            "Gemini image quota exceeded on the configured API key. "
            "Used Cloudflare Flux instead. Fix STUDIO_IMAGE_GEMINI_API_KEY billing "
            "or wait for quota reset to prefer Gemini again."
        )
    elif reason == "auth":
        result["model"] = f"{model} (Gemini auth fallback)"
        result["fallback_reason"] = (
            "STUDIO_IMAGE_GEMINI_API_KEY was rejected (401). Used Cloudflare Flux instead. "
            "In AI Studio, restrict the key to 'Gemini API only' (AQ... and AIza... keys both work), "
            "save STUDIO_IMAGE_GEMINI_API_KEY in .env, and restart the backend."
        )
    else:
        result["fallback_reason"] = reason
    return result


def generate_image(prompt: str) -> dict:
    """Generate an image using IMAGE_PROVIDER (default: gemini-first)."""
    provider = resolve_image_provider()

    if provider == "gemini":
        limit = _gemini_priority_limit()
        day, used = _read_gemini_daily_count()
        cloudflare_ready = _cloudflare_image_ready()

        # After the daily Gemini budget, prefer Cloudflare directly.
        if limit > 0 and used >= limit and cloudflare_ready:
            logger.info(
                f"Gemini daily image budget reached ({used}/{limit} on {day}); "
                "using Cloudflare Flux."
            )
            return _cloudflare_result(prompt, reason="daily_budget")

        # Otherwise always try Gemini first.
        try:
            result = generate_gemini_image(prompt)
            result["provider"] = "gemini"
            result["fallback_reason"] = None
            new_count = _increment_gemini_daily_count()
            logger.info(
                f"Gemini image generated successfully "
                f"({new_count}/{limit or '∞'} today)."
            )
            return result
        except LLMConnectionError as exc:
            if cloudflare_ready and _is_gemini_auth_error(exc):
                logger.warning(
                    "Gemini image auth error; falling back to Cloudflare. "
                    f"Reason: {exc}"
                )
                return _cloudflare_result(prompt, reason="auth")
            if cloudflare_ready and _is_gemini_quota_error(exc):
                logger.warning(
                    "Gemini image quota/billing error; falling back to Cloudflare. "
                    f"Reason: {exc}"
                )
                return _cloudflare_result(prompt, reason="quota")
            raise

    if provider == "modelslab":
        result = generate_modelslab_image(prompt)
        result["provider"] = result.get("provider") or "modelslab"
        return result
    if provider == "cloudflare":
        result = generate_cloudflare_image(prompt)
        result["provider"] = "cloudflare"
        return result

    raise LLMConnectionError(
        f"Image provider '{provider}' is not supported. "
        "Set IMAGE_PROVIDER=gemini and ensure STUDIO_IMAGE_GEMINI_API_KEY "
        "(or CREATION_GEMINI_API_KEY) is set."
    )


__all__ = ["extract_image_prompt", "generate_image"]
