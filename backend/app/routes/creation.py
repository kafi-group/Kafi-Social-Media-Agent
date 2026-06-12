"""
API Routes - Content Creation (chatbot)
GET  /creation/models - Chat model info + Gemini web link
POST /creation/chat   - Chat via dedicated CREATION_GEMINI_API_KEY

Image and video creation open Google Gemini in the browser (GEMINI_WEB_URL).
"""

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.llm.ollama_client import LLMClient
from app.schemas.creation import (
    ChatRequest,
    ChatResponse,
    CreationModelsResponse,
    ModelInfo,
)
from app.utils.exceptions import LLMConnectionError
from app.utils.logger import logger

router = APIRouter()

chat_client = LLMClient()


def _creation_model_label() -> str:
    """Human-readable label for the Content Creation Gemini model."""
    name = settings.CREATION_GEMINI_MODEL.replace("gemini-", "Gemini ").replace("-", " ")
    return name.title()


@router.get("/creation/models", response_model=CreationModelsResponse)
async def list_creation_models():
    """Return the Content Creation chat model and the Gemini web link for image/video."""
    return CreationModelsResponse(
        models=[
            ModelInfo(id=settings.CREATION_GEMINI_MODEL, label=_creation_model_label()),
        ],
        gemini_web_url=settings.GEMINI_WEB_URL,
        chat_ready=bool(settings.CREATION_GEMINI_API_KEY),
    )


@router.post("/creation/chat", response_model=ChatResponse)
async def creation_chat(request: ChatRequest):
    """Chat with Google Gemini using CREATION_GEMINI_API_KEY (separate from Content Posting)."""
    try:
        messages = [{"role": m.role.value, "content": m.content} for m in request.messages]
        reply, model = chat_client.chat(
            messages,
            api_key=settings.CREATION_GEMINI_API_KEY,
            model=settings.CREATION_GEMINI_MODEL,
            fallback_model=settings.CREATION_GEMINI_FALLBACK_MODEL,
        )
        return ChatResponse(model=model, reply=reply)
    except LLMConnectionError as e:
        logger.error(f"Creation chat error: {str(e)}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Creation chat unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
