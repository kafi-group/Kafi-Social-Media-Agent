"""
Gemini native image generation for Prompt Studio.

Uses STUDIO_IMAGE_GEMINI_API_KEY — isolated from chat/posting Gemini keys.
"""

from __future__ import annotations

import base64
import re
import time
from typing import Optional

import requests

from app.config import get_image_gemini_api_keys, get_image_gemini_models, settings
from app.services.media import MediaService
from app.utils.exceptions import ContentGenerationError, LLMConnectionError
from app.utils.logger import logger

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_auth_error_message(message: str) -> bool:
    lowered = message.lower()
    return any(
        term in lowered
        for term in ("401", "403", "rejected by google", "invalid authentication", "unauthenticated")
    )


def _is_quota_error_message(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in ("quota", "billing", "rate limit", "429"))


def extract_image_prompt(text: str) -> str:
    """
    Pull the Meta AI prompt block from an assistant reply, or fall back to full text.
    """
    if not text.strip():
        raise ContentGenerationError("No prompt text provided.")

    patterns = [
        r"\*\*Meta AI prompt:\*\*\s*\n([\s\S]*?)(?=\n\*\*Notes:\*\*|\n---|\Z)",
        r"\*\*Meta AI prompt:\*\*\s*([\s\S]*?)(?=\n\*\*Notes:\*\*|\n---|\Z)",
        r"Meta AI prompt:\s*\n([\s\S]*?)(?=\n\*\*Notes:\*\*|\n---|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            prompt = match.group(1).strip()
            if prompt:
                return prompt[:4000]

    cleaned = text.strip()
    if len(cleaned) > 4000:
        cleaned = cleaned[:4000]
    return cleaned


def generate_image(prompt: str) -> dict:
    """
    Generate an image via Gemini and store it in uploads/Supabase.

    Returns:
        dict with media_path, media_url, model, optional caption text
    """
    api_keys = get_image_gemini_api_keys()
    if not api_keys:
        raise LLMConnectionError(
            "Image generation is not configured. "
            "Set IMAGE_PROVIDER=gemini and STUDIO_IMAGE_GEMINI_API_KEY "
            "(or CREATION_GEMINI_API_KEY / GEMINI_API_KEY) in backend .env."
        )

    models = get_image_gemini_models()
    if not models:
        raise LLMConnectionError("No IMAGE_GEMINI_MODEL configured.")

    last_error: Exception | None = None
    for key_index, api_key in enumerate(api_keys):
        key_label = (
            "STUDIO_IMAGE_GEMINI_API_KEY" if key_index == 0 else f"fallback key #{key_index + 1}"
        )
        for model in models:
            try:
                image_bytes, mime_type, caption = _generate_with_model(
                    prompt, model, api_key, key_label=key_label
                )
                media_service = MediaService()
                stored = media_service.save_bytes(
                    image_bytes,
                    extension=_extension_for_mime(mime_type),
                    media_type="image",
                    original_name="gemini-generated.png",
                )
                return {
                    "media_path": stored["media_path"],
                    "media_url": stored["media_url"],
                    "model": model,
                    "provider": "gemini",
                    "caption": caption,
                }
            except (LLMConnectionError, ContentGenerationError) as exc:
                last_error = exc
                logger.warning(f"Gemini image model {model} ({key_label}) failed: {exc}")
                message = str(exc)
                if _is_auth_error_message(message):
                    logger.warning(
                        f"Gemini image key rejected ({key_label}); trying next configured key."
                    )
                    break
                if _is_quota_error_message(message):
                    logger.warning(
                        f"Gemini image quota hit on {key_label}; trying next configured key."
                    )
                    break
                if "not available" in message.lower() or "404" in message:
                    continue

    raise LLMConnectionError(f"Image generation failed: {last_error}") from last_error


def _extension_for_mime(mime_type: str) -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }
    return mapping.get(mime_type.lower(), ".png")


def _gemini_generate_content(
    model: str,
    api_key: str,
    payload: dict,
    *,
    timeout: int,
) -> requests.Response:
    """
    Call Gemini generateContent with auth styles compatible with both
    legacy AIza keys (?key= query) and newer AQ authorization keys (header).
    """
    base_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    headers = {"Content-Type": "application/json"}

    # New Google AI Studio auth keys (AQ...) — official REST uses x-goog-api-key.
    response = requests.post(
        base_url,
        headers={**headers, "x-goog-api-key": api_key},
        json=payload,
        timeout=timeout,
    )
    if response.status_code not in (401, 403):
        return response

    # Legacy fallback for older AIza keys.
    logger.warning(
        f"Gemini image auth via x-goog-api-key failed ({response.status_code}); "
        "retrying with ?key= query parameter."
    )
    return requests.post(
        f"{base_url}?key={api_key}",
        headers=headers,
        json=payload,
        timeout=timeout,
    )


def _generate_with_model(
    prompt: str,
    model: str,
    api_key: str,
    *,
    key_label: str = "STUDIO_IMAGE_GEMINI_API_KEY",
) -> tuple[bytes, str, Optional[str]]:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    max_retries = settings.GEMINI_MAX_RETRIES
    for attempt in range(1, max_retries + 1):
        try:
            response = _gemini_generate_content(
                model,
                api_key,
                payload,
                timeout=settings.IMAGE_GEMINI_TIMEOUT,
            )

            if response.status_code in (401, 403):
                raise LLMConnectionError(
                    f"{key_label} was rejected by Google (401/403). "
                    "The key may be revoked, blocked, or missing 'Restrict to Gemini API only' "
                    "in AI Studio. AQ... and AIza... keys are both valid formats."
                )

            if response.status_code == 429:
                detail = response.text[:500]
                if "quota" in detail.lower() or "billing" in detail.lower():
                    raise LLMConnectionError(
                        f"Gemini image quota exceeded on {key_label}. "
                        "Image models often require billing enabled on that Google project — "
                        "check https://aistudio.google.com/apikey or wait for daily quota reset."
                    )
                raise LLMConnectionError(
                    "Gemini image API rate limit exceeded. Try again in a minute."
                )

            if response.status_code == 404:
                raise LLMConnectionError(
                    f"Image model '{model}' is not available. "
                    "Trying next fallback in IMAGE_GEMINI_FALLBACK_MODELS "
                    "(up to 3 fallbacks; recommended primary: gemini-2.5-flash-image)."
                )

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = 2 ** attempt
                logger.warning(
                    f"Gemini image {model} returned {response.status_code}; retry in {delay}s"
                )
                time.sleep(delay)
                continue

            if not response.ok:
                detail = response.text[:400]
                raise LLMConnectionError(
                    f"Gemini image API error ({response.status_code}): {detail}"
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMConnectionError(
                    f"Gemini returned no image candidates: {str(data)[:200]}"
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            image_bytes: bytes | None = None
            mime_type = "image/png"
            caption_parts: list[str] = []

            for part in parts:
                text = part.get("text")
                if text:
                    caption_parts.append(text.strip())

                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    mime_type = inline.get("mimeType") or inline.get("mime_type") or mime_type
                    image_bytes = base64.b64decode(inline["data"])

            if not image_bytes:
                raise LLMConnectionError(
                    "Gemini completed but returned no image data. "
                    "Check IMAGE_GEMINI_MODEL supports image output."
                )

            caption = "\n".join(caption_parts).strip() or None
            return image_bytes, mime_type, caption

        except requests.exceptions.Timeout as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise LLMConnectionError(
                f"Gemini image request timed out after {settings.IMAGE_GEMINI_TIMEOUT}s"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise LLMConnectionError(f"Gemini image request failed: {exc}") from exc

    raise LLMConnectionError(f"Gemini image failed after {max_retries} attempts")
