"""
API Routes - Content Creation (chatbot)
GET  /creation/models          - Capabilities + external video links
POST /creation/chat            - Prompt engineering chat (CREATION_GEMINI_API_KEY)
POST /creation/generate-image  - Image gen (provider per IMAGE_PROVIDER)
POST /creation/generate-voice  - edge-tts voice-over (free)
"""

from fastapi import APIRouter, HTTPException, Request

from app.config import (
    get_creation_gemini_api_keys,
    get_creation_gemini_models,
    get_image_generation_model_label,
    is_image_generation_ready,
    settings,
)
from app.llm.ollama_client import LLMClient
from app.middleware.rate_limiter import limiter
from app.schemas.creation import (
    ChatRequest,
    ChatResponse,
    CreationIntent,
    CreationModelsResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,
    MatchedProduct,
    ModelInfo,
    VoiceGenerateRequest,
    VoiceGenerateResponse,
)
from app.services.image_generation import extract_image_prompt, generate_image
from app.services.product_knowledge import (
    build_system_prompt,
    infer_prompt_media_type,
    product_for_query,
)
from app.services.voice_tts import MOOD_PRESETS, generate_voice_async, list_voice_moods
from app.utils.exceptions import ContentGenerationError, LLMConnectionError
from app.utils.logger import logger

router = APIRouter()

chat_client = LLMClient()


def _creation_model_label() -> str:
    """Human-readable label for the Content Creation Gemini model."""
    name = settings.CREATION_GEMINI_MODEL.replace("gemini-", "Gemini ").replace("-", " ")
    return name.title()


def _resolve_media_url(media_url: str, request: Request) -> str:
    """Turn relative /uploads/ paths into absolute URLs for the frontend."""
    if not media_url:
        return media_url
    if media_url.startswith("http://") or media_url.startswith("https://"):
        return media_url
    base = str(request.base_url).rstrip("/")
    if media_url.startswith("/"):
        return f"{base}{media_url}"
    return f"{base}/{media_url}"


@router.get("/creation/models", response_model=CreationModelsResponse)
async def list_creation_models():
    """Return chat/image/voice capabilities and external video tool links."""
    image_ready = is_image_generation_ready()
    return CreationModelsResponse(
        models=[
            ModelInfo(id=settings.CREATION_GEMINI_MODEL, label=_creation_model_label()),
        ],
        gemini_web_url=settings.GEMINI_WEB_URL,
        meta_ai_web_url=settings.META_AI_WEB_URL,
        elevenlabs_web_url=settings.ELEVENLABS_WEB_URL,
        google_flow_characters_url=settings.GOOGLE_FLOW_CHARACTERS_URL,
        google_flow_final_product_url=settings.GOOGLE_FLOW_FINAL_PRODUCT_URL,
        chat_ready=bool(get_creation_gemini_api_keys()),
        image_ready=image_ready,
        image_model=get_image_generation_model_label() if image_ready else "",
        voice_ready=True,
        voice_moods=list_voice_moods(),
    )


@router.post("/creation/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def creation_chat(request: Request, body: ChatRequest):
    """Chat with Gemini using CREATION_GEMINI_API_KEY (prompt engineering)."""
    try:
        last_user_text = ""
        has_reference_image = False
        for m in body.messages:
            if m.role.value == "user":
                if m.image_base64 and m.image_base64.strip():
                    has_reference_image = True
        for m in reversed(body.messages):
            if m.role.value == "user":
                last_user_text = m.content
                break

        matched = product_for_query(last_user_text) if last_user_text else None

        if body.intent == CreationIntent.CREATE_IMAGE:
            media_type = "image"
        elif body.intent == CreationIntent.CREATE_VOICE:
            media_type = None
        else:
            media_type = infer_prompt_media_type(last_user_text) if last_user_text else None

        system_prompt = build_system_prompt(
            matched,
            media_type=media_type,
            intent=body.intent,
            has_reference_image=has_reference_image,
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in body.messages:
            entry: dict = {"role": m.role.value, "content": m.content}
            if m.image_base64 and m.image_base64.strip():
                if len(m.image_base64) > 5_500_000:
                    raise HTTPException(
                        status_code=400,
                        detail="Reference image is too large. Use an image under 4 MB.",
                    )
                entry["image_base64"] = m.image_base64.strip()
                entry["image_mime_type"] = (m.image_mime_type or "image/jpeg").strip()
            messages.append(entry)

        reply, model = chat_client.chat(
            messages,
            api_keys=get_creation_gemini_api_keys(),
            models=get_creation_gemini_models(),
        )

        matched_product_payload: MatchedProduct | None = None
        if matched:
            matched_product_payload = MatchedProduct(
                id=matched["id"],
                name=matched["name"],
                brand=matched.get("brand", "Essence"),
                category=matched.get("category", ""),
                description=matched.get("description", ""),
                packaging=matched.get("packaging", []),
            )

        return ChatResponse(
            model=model,
            reply=reply,
            matched_product=matched_product_payload,
            intent=body.intent,
        )

    except LLMConnectionError as e:
        logger.error(f"Creation chat error: {str(e)}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Creation chat unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/creation/generate-image", response_model=ImageGenerateResponse)
@limiter.limit("10/minute")
async def creation_generate_image(request: Request, body: ImageGenerateRequest):
    """Generate a product image via IMAGE_PROVIDER (gemini, modelslab, or cloudflare)."""
    try:
        prompt = extract_image_prompt(body.prompt)
        result = generate_image(prompt)
        return ImageGenerateResponse(
            media_path=result["media_path"],
            media_url=_resolve_media_url(result["media_url"], request),
            model=result["model"],
            caption=result.get("caption"),
        )
    except ContentGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")


@router.post("/creation/generate-voice", response_model=VoiceGenerateResponse)
@limiter.limit("15/minute")
async def creation_generate_voice(request: Request, body: VoiceGenerateRequest):
    """Generate voice-over MP3 via edge-tts (free)."""
    mood = body.mood.strip().lower()
    if mood not in MOOD_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mood '{body.mood}'. Choose: {', '.join(MOOD_PRESETS.keys())}",
        )

    try:
        result = await generate_voice_async(body.text, mood=mood)  # type: ignore[arg-type]
        return VoiceGenerateResponse(
            media_path=result["media_path"],
            media_url=_resolve_media_url(result["media_url"], request),
            mood=result["mood"],
            voice=result["voice"],
            script_preview=result["script_preview"],
        )
    except ContentGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Voice generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {e}")
