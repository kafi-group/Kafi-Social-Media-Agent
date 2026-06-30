"""
LLM Client Module
Uses Google Gemini API for AI content generation.
Fast, free tier: 1,500 requests/day.

Get a free API key at https://aistudio.google.com/apikey
Set GEMINI_API_KEY in your .env file.
"""

import json
import time

import requests

from app.config import settings
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger

# HTTP status codes worth retrying (transient Gemini overload / server errors)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMClient:
    """
    LLM client for AI content generation via Google Gemini API.

    Gemini is the sole provider — fast, free, no local model needed.
    """

    def __init__(self):
        self.temperature = settings.TEMPERATURE

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Google Gemini API.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional parameters (temperature, max_output_tokens,
                      response_mime_type, etc.)

        Returns:
            Generated text string

        Raises:
            LLMConnectionError: If generation fails
        """
        temperature = kwargs.get("temperature", self.temperature)
        max_output_tokens = kwargs.get("max_output_tokens", settings.MAX_TOKENS)
        response_mime_type = kwargs.get("response_mime_type")
        return self._generate_gemini(
            prompt,
            temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

    def chat(
        self,
        messages: list[dict],
        *,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        models: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Multi-turn chat via Google Gemini API.

        Args:
            messages: List of {role, content} with roles user/assistant/system.
            api_key: Optional single-key override (e.g. CREATION_GEMINI_API_KEY).
            api_keys: Optional ordered key list; tries each key after all models fail.
            model: Optional primary model override.
            fallback_model: Optional fallback model override.
            models: Optional ordered model list; overrides model + fallback_model.

        Returns:
            Tuple of (reply text, model id used).
        """
        if api_keys:
            keys = [k.strip() for k in api_keys if k.strip()]
        else:
            single = (api_key or settings.GEMINI_API_KEY).strip()
            keys = [single] if single else []

        if not keys:
            raise LLMConnectionError(
                "Gemini API key not configured. "
                "Set GEMINI_API_KEY or CREATION_GEMINI_API_KEY in your .env file. "
                "Get a free key at https://aistudio.google.com/apikey"
            )

        system_instruction: dict | None = None
        contents: list[dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = (msg.get("content") or "").strip()
            image_b64 = (msg.get("image_base64") or "").strip()
            image_mime = (msg.get("image_mime_type") or "image/jpeg").strip()
            if not text and not image_b64:
                continue
            if role == "system":
                system_instruction = {"parts": [{"text": text}]}
                continue
            parts: list[dict] = []
            if text:
                parts.append({"text": text})
            if image_b64:
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": image_mime,
                            "data": image_b64,
                        }
                    }
                )
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        if not contents:
            raise LLMConnectionError("No messages to send.")

        if models:
            model_chain = [m.strip() for m in models if m.strip()]
        else:
            primary = (model or settings.GEMINI_MODEL).strip()
            fb = (fallback_model or settings.GEMINI_FALLBACK_MODEL).strip()
            model_chain = [primary]
            if fb and fb not in model_chain:
                model_chain.append(fb)

        if not model_chain:
            raise LLMConnectionError("No Gemini models configured for chat.")

        last_error: Exception | None = None
        for key_index, key in enumerate(keys):
            for model_index, model_id in enumerate(model_chain):
                try:
                    reply = self._chat_gemini_with_retries(
                        contents,
                        model_id,
                        api_key=key,
                        system_instruction=system_instruction,
                    )
                    return reply, model_id
                except LLMConnectionError as e:
                    last_error = e
                    has_next_model = model_index < len(model_chain) - 1
                    has_next_key = key_index < len(keys) - 1
                    if has_next_model:
                        logger.warning(
                            f"Gemini chat model {model_id} failed ({e}). "
                            f"Trying fallback model: {model_chain[model_index + 1]}"
                        )
                        continue
                    if has_next_key:
                        logger.warning(
                            f"All models failed on current API key ({e}). "
                            "Trying next CREATION_GEMINI_API_KEYS entry."
                        )
                        break
                    raise

        raise LLMConnectionError(f"Gemini chat failed: {last_error}") from last_error

    def _chat_gemini_with_retries(
        self,
        contents: list[dict],
        model: str,
        *,
        api_key: str,
        system_instruction: dict | None = None,
    ) -> str:
        """Call Gemini with a multi-turn conversation."""
        logger.info(f"Gemini chat (model: {model}, turns: {len(contents)})")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
            f"?key={api_key}"
        )

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": settings.MAX_TOKENS,
                "topP": settings.TOP_P,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        max_retries = settings.GEMINI_MAX_RETRIES
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=settings.GEMINI_TIMEOUT,
                )

                if response.status_code == 429:
                    raise LLMConnectionError(
                        "Gemini API rate limit exceeded. "
                        "Free tier allows ~1,500 requests/day. "
                        "Try again shortly."
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    error_msg = response.text[:200]
                    if attempt < max_retries:
                        delay = 2 ** attempt
                        logger.warning(
                            f"Gemini chat {model} returned {response.status_code} "
                            f"(attempt {attempt}/{max_retries}). Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    raise LLMConnectionError(
                        f"Gemini API unavailable ({response.status_code}): {error_msg}"
                    )

                response.raise_for_status()
                data = response.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMConnectionError(
                        f"Gemini returned no candidates. Response: {json.dumps(data)[:200]}"
                    )

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMConnectionError("Gemini returned empty content")

                return parts[0].get("text", "")

            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.warning(
                        f"Gemini chat {model} timed out (attempt {attempt}/{max_retries}). "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue
                raise LLMConnectionError(
                    f"Gemini API request timed out after {settings.GEMINI_TIMEOUT}s"
                ) from e
            except LLMConnectionError:
                raise
            except requests.exceptions.RequestException as e:
                raise LLMConnectionError(f"Gemini API request failed: {str(e)}") from e

        raise LLMConnectionError(f"Gemini chat failed after {max_retries} attempts")

    def _generate_gemini(
        self,
        prompt: str,
        temperature: float,
        *,
        max_output_tokens: int = settings.MAX_TOKENS,
        response_mime_type: str | None = None,
    ) -> str:
        """Generate text via Google Gemini API (free, fast)."""
        if not settings.GEMINI_API_KEY:
            raise LLMConnectionError(
                "Gemini API key not configured. "
                "Set GEMINI_API_KEY in your .env file. "
                "Get a free key at https://aistudio.google.com/apikey"
            )

        models = [settings.GEMINI_MODEL]
        if settings.GEMINI_FALLBACK_MODEL and settings.GEMINI_FALLBACK_MODEL not in models:
            models.append(settings.GEMINI_FALLBACK_MODEL)

        last_error: Exception | None = None
        for model_index, model in enumerate(models):
            try:
                return self._generate_gemini_with_retries(
                    prompt,
                    temperature,
                    model,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                )
            except LLMConnectionError as e:
                last_error = e
                if model_index < len(models) - 1:
                    logger.warning(
                        f"Gemini model {model} failed ({e}). "
                        f"Trying fallback: {models[model_index + 1]}"
                    )
                    continue
                raise

        raise LLMConnectionError(f"Gemini API request failed: {last_error}") from last_error

    def _generate_gemini_with_retries(
        self,
        prompt: str,
        temperature: float,
        model: str,
        *,
        max_output_tokens: int = settings.MAX_TOKENS,
        response_mime_type: str | None = None,
    ) -> str:
        """Call a single Gemini model with retries for transient failures."""
        logger.info(f"Generating via Google Gemini (model: {model})")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )

        generation_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "topP": settings.TOP_P,
        }
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": generation_config,
        }

        max_retries = settings.GEMINI_MAX_RETRIES
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=settings.GEMINI_TIMEOUT,
                )

                if response.status_code == 429:
                    raise LLMConnectionError(
                        "Gemini API rate limit exceeded. "
                        "Free tier allows ~1,500 requests/day. "
                        "Try again tomorrow."
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    error_msg = response.text[:200]
                    if attempt < max_retries:
                        delay = 2 ** attempt
                        logger.warning(
                            f"Gemini {model} returned {response.status_code} "
                            f"(attempt {attempt}/{max_retries}). Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    raise LLMConnectionError(
                        f"Gemini API unavailable ({response.status_code}): {error_msg}"
                    )

                response.raise_for_status()
                data = response.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMConnectionError(
                        f"Gemini returned no candidates. Response: {json.dumps(data)[:200]}"
                    )

                finish_reason = candidates[0].get("finishReason")
                if finish_reason == "MAX_TOKENS":
                    logger.warning(
                        f"Gemini {model} hit maxOutputTokens ({max_output_tokens}); "
                        "response may be truncated"
                    )

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMConnectionError("Gemini returned empty content")

                return parts[0].get("text", "")

            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.warning(
                        f"Gemini {model} timed out (attempt {attempt}/{max_retries}). "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue
                raise LLMConnectionError(
                    f"Gemini API request timed out after {settings.GEMINI_TIMEOUT}s"
                ) from e
            except requests.exceptions.RequestException as e:
                raise LLMConnectionError(f"Gemini API request failed: {str(e)}") from e

        raise LLMConnectionError(f"Gemini API request failed after {max_retries} attempts")

    def health_check(self) -> bool:
        """Check if the Gemini API key is configured."""
        return bool(settings.GEMINI_API_KEY)


# Keep backward compatibility alias
OllamaClient = LLMClient
