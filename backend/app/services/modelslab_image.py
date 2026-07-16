"""
ModelsLab text-to-image for Prompt Studio (e.g. HiDream O1).

Docs: https://docs.modelslab.com/image-generation/hidream-o1/text-to-image
"""

from __future__ import annotations

import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from app.config import settings
from app.services.media import MediaService
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger

_TEXT2IMG_URL = "https://modelslab.com/api/v6/images/text2img"
_POLL_INTERVAL_SEC = 3


def _normalize_model_id(model_id: str) -> str:
    """Map UI names like hidream-o1-text to ModelsLab model_id."""
    mid = model_id.strip().lower()
    aliases = {
        "hidream-o1-text": "hidream-o1",
        "hidream-o1-text2img": "hidream-o1",
        "hidream_o1": "hidream-o1",
    }
    return aliases.get(mid, model_id.strip())


def _fetch_image_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LLMConnectionError("ModelsLab returned an invalid image URL.")

    response = requests.get(url, timeout=timeout)
    if not response.ok:
        raise LLMConnectionError(
            f"Failed to download ModelsLab image ({response.status_code})."
        )

    content_type = (response.headers.get("Content-Type") or "image/png").split(";")[0]
    return response.content, content_type


def _pick_image_url(data: dict[str, Any]) -> str:
    for key in ("output", "proxy_links", "future_links"):
        items = data.get(key) or []
        for item in items:
            if isinstance(item, str) and item.startswith("http"):
                return item
    raise LLMConnectionError("ModelsLab completed but returned no image URL.")


def _poll_until_ready(request_id: int, api_key: str, timeout: int) -> dict[str, Any]:
    fetch_url = f"https://modelslab.com/api/v6/images/fetch/{request_id}"
    deadline = time.time() + timeout

    while time.time() < deadline:
        response = requests.post(
            fetch_url,
            json={"key": api_key},
            timeout=min(60, timeout),
        )
        if not response.ok:
            detail = response.text[:300]
            raise LLMConnectionError(
                f"ModelsLab fetch error ({response.status_code}): {detail}"
            )

        data = response.json()
        status = (data.get("status") or "").lower()

        if status == "success":
            return data
        if status == "error":
            raise LLMConnectionError(
                data.get("message") or data.get("messege") or "ModelsLab image generation failed."
            )

        time.sleep(_POLL_INTERVAL_SEC)

    raise LLMConnectionError(
        f"ModelsLab image generation timed out after {timeout}s. Try again shortly."
    )


def generate_modelslab_image(prompt: str) -> dict:
    """
    Generate an image via ModelsLab text2img and store it in uploads/Supabase.

    Returns:
        dict with media_path, media_url, model, optional caption
    """
    api_key = settings.MODELSLAB_API_KEY.strip()
    if not api_key:
        raise LLMConnectionError(
            "ModelsLab is not configured. Set MODELSLAB_API_KEY in backend .env "
            "(free signup at https://modelslab.com — no credit card on free tier)."
        )

    model_id = _normalize_model_id(settings.MODELSLAB_IMAGE_MODEL)
    timeout = settings.MODELSLAB_IMAGE_TIMEOUT

    payload: dict[str, Any] = {
        "key": api_key,
        "model_id": model_id,
        "prompt": prompt[:4000],
        "negative_prompt": settings.MODELSLAB_NEGATIVE_PROMPT,
        "width": str(settings.MODELSLAB_IMAGE_WIDTH),
        "height": str(settings.MODELSLAB_IMAGE_HEIGHT),
        "samples": 1,
        "num_inference_steps": settings.MODELSLAB_INFERENCE_STEPS,
        "guidance_scale": settings.MODELSLAB_GUIDANCE_SCALE,
        "safety_checker": "no",
        "seed": None,
        "clip_skip": settings.MODELSLAB_CLIP_SKIP,
    }

    logger.info(f"ModelsLab text2img (model: {model_id})")

    try:
        response = requests.post(_TEXT2IMG_URL, json=payload, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise LLMConnectionError(
            f"ModelsLab request timed out after {timeout}s"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise LLMConnectionError(f"ModelsLab request failed: {exc}") from exc

    if response.status_code == 401:
        raise LLMConnectionError("ModelsLab API key is invalid. Check MODELSLAB_API_KEY in .env.")

    if not response.ok:
        raise LLMConnectionError(
            f"ModelsLab API error ({response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    status = (data.get("status") or "").lower()

    if status == "error":
        raise LLMConnectionError(
            data.get("message") or data.get("messege") or "ModelsLab image generation failed."
        )

    if status == "processing":
        request_id = data.get("id")
        if request_id is None:
            raise LLMConnectionError("ModelsLab is processing but returned no request id.")
        logger.info(f"ModelsLab processing job {request_id}, polling…")
        data = _poll_until_ready(int(request_id), api_key, timeout)
        status = (data.get("status") or "").lower()

    if status != "success":
        raise LLMConnectionError(
            f"ModelsLab image generation failed (status: {data.get('status')})."
        )

    image_url = _pick_image_url(data)
    image_bytes, mime_type = _fetch_image_bytes(image_url, timeout=60)

    ext = ".png"
    if "jpeg" in mime_type or "jpg" in mime_type:
        ext = ".jpg"
    elif "webp" in mime_type:
        ext = ".webp"

    stored = MediaService().save_bytes(
        image_bytes,
        extension=ext,
        media_type="image",
        original_name=f"modelslab-{model_id}{ext}",
    )

    caption: Optional[str] = None
    if data.get("nsfw_content_detected"):
        caption = "Note: ModelsLab flagged possible NSFW content in this output."

    return {
        "media_path": stored["media_path"],
        "media_url": stored["media_url"],
        "model": f"modelslab/{model_id}",
        "provider": "modelslab",
        "caption": caption,
    }
