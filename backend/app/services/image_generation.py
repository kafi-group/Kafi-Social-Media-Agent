"""
Prompt Studio image generation — routes by IMAGE_PROVIDER (gemini, modelslab, cloudflare).
"""

from __future__ import annotations

from app.config import settings
from app.services.cloudflare_image import generate_cloudflare_image
from app.services.gemini_image import extract_image_prompt, generate_image as generate_gemini_image
from app.services.modelslab_image import generate_modelslab_image
from app.utils.exceptions import LLMConnectionError


def generate_image(prompt: str) -> dict:
    """Generate an image using the configured IMAGE_PROVIDER."""
    provider = (settings.IMAGE_PROVIDER or "gemini").strip().lower()

    if provider == "modelslab":
        return generate_modelslab_image(prompt)
    if provider == "gemini":
        return generate_gemini_image(prompt)
    if provider == "cloudflare":
        return generate_cloudflare_image(prompt)

    raise LLMConnectionError(
        f"Unknown IMAGE_PROVIDER '{settings.IMAGE_PROVIDER}'. "
        "Use 'gemini', 'modelslab', or 'cloudflare'."
    )


__all__ = ["extract_image_prompt", "generate_image"]
