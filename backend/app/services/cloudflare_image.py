"""
Cloudflare Workers AI text-to-image for Prompt Studio.

Docs: https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
"""

from __future__ import annotations

import base64
from typing import Any

import requests

from app.config import settings
from app.services.media import MediaService
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger


def _model_path(model: str) -> str:
    """REST path segment — ensure @cf/... format."""
    path = model.strip()
    if path and not path.startswith("@"):
        path = f"@{path}"
    return path


def generate_cloudflare_image(prompt: str) -> dict:
    """
    Generate an image via Cloudflare Workers AI and store it in uploads/Supabase.

    Returns:
        dict with media_path, media_url, model, optional caption
    """
    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    api_token = settings.CLOUDFLARE_API_TOKEN.strip()
    model = settings.CLOUDFLARE_IMAGE_MODEL.strip() or "@cf/black-forest-labs/flux-1-schnell"

    if not account_id or not api_token:
        raise LLMConnectionError(
            "Cloudflare image generation is not configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in backend .env."
        )

    model_path = _model_path(model)
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}"
    payload: dict[str, Any] = {
        "prompt": prompt[:2048],
        "steps": settings.CLOUDFLARE_IMAGE_STEPS,
    }

    logger.info(f"Cloudflare Workers AI image gen (model: {model})")

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.CLOUDFLARE_IMAGE_TIMEOUT,
        )
    except requests.exceptions.Timeout as exc:
        raise LLMConnectionError(
            f"Cloudflare request timed out after {settings.CLOUDFLARE_IMAGE_TIMEOUT}s"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise LLMConnectionError(f"Cloudflare request failed: {exc}") from exc

    if response.status_code == 401:
        raise LLMConnectionError(
            "Cloudflare API token is invalid. Check CLOUDFLARE_API_TOKEN in .env."
        )

    if not response.ok:
        raise LLMConnectionError(
            f"Cloudflare API error ({response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    if not data.get("success"):
        errors = data.get("errors") or data
        raise LLMConnectionError(f"Cloudflare generation failed: {errors}")

    result = data.get("result") or {}
    image_b64 = result.get("image")
    if not image_b64:
        raise LLMConnectionError("Cloudflare returned no image data.")

    try:
        image_bytes = base64.b64decode(image_b64)
    except (ValueError, TypeError) as exc:
        raise LLMConnectionError("Cloudflare returned invalid base64 image data.") from exc

    stored = MediaService().save_bytes(
        image_bytes,
        extension=".jpg",
        media_type="image",
        original_name="cloudflare-generated.jpg",
    )

    return {
        "media_path": stored["media_path"],
        "media_url": stored["media_url"],
        "model": model,
        "caption": None,
    }
