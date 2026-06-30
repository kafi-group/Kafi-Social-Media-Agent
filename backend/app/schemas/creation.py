"""
Pydantic Schemas - Content Creation (chatbot + image generation)
"""

from enum import Enum as PyEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreationIntent(str, PyEnum):
    """What the user wants Prompt Studio to do for this message."""

    PROMPT = "prompt"  # write prompts (default)
    CREATE_IMAGE = "create_image"  # build prompt + in-app Gemini image
    CREATE_VOICE = "create_voice"  # build script + in-app TTS
    VIDEO_PROMPT = "video_prompt"  # Meta AI / Flow video prompts only


class ChatRole(str, PyEnum):
    """Chat message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single chat message."""

    role: ChatRole
    content: str
    # Optional reference image (user messages only) — sent to Gemini vision for prompt writing.
    image_base64: Optional[str] = Field(
        default=None,
        description="Base64 image bytes (no data-URL prefix). Max ~4MB decoded.",
    )
    image_mime_type: Optional[str] = Field(
        default=None,
        description="e.g. image/jpeg, image/png, image/webp",
    )


class ChatRequest(BaseModel):
    """Request body for the chatbot."""

    model: str = Field(default="", description="Ignored — chat uses GEMINI_MODEL from config.")
    intent: CreationIntent = Field(
        default=CreationIntent.PROMPT,
        description="User-selected mode: prompt, create_image, create_voice, or video_prompt.",
    )
    messages: list[ChatMessage] = Field(..., min_length=1)


class MatchedProduct(BaseModel):
    """A product that was detected in the user's message."""

    id: str
    name: str
    brand: str
    category: str
    description: str
    packaging: list[str]


class ChatResponse(BaseModel):
    """Chatbot reply."""

    model: str
    reply: str
    matched_product: Optional[MatchedProduct] = None
    intent: CreationIntent = CreationIntent.PROMPT


class ModelInfo(BaseModel):
    """A selectable chat model."""

    id: str
    label: str


class CreationModelsResponse(BaseModel):
    """Available chat models + generation capabilities."""

    models: list[ModelInfo]
    gemini_web_url: str
    meta_ai_web_url: str = "https://www.meta.ai/"
    elevenlabs_web_url: str = "https://elevenlabs.io/app/speech-synthesis/text-to-speech"
    google_flow_characters_url: str = (
        "https://labs.google/fx/tools/flow/project/cc16a3ce-33ec-4248-bb1a-3341c7817479/characters"
    )
    google_flow_final_product_url: str = (
        "https://labs.google/fx/tools/flow/project/0b5aa7ed-bd40-490d-af9a-24208f855710"
    )
    chat_ready: bool
    image_ready: bool = False
    image_model: str = ""
    voice_ready: bool = True
    voice_moods: list[dict[str, str]] = Field(default_factory=list)


class ImageGenerateRequest(BaseModel):
    """Generate an image from prompt text (usually extracted from chat reply)."""

    prompt: str = Field(..., min_length=3, max_length=4000)


class ImageGenerateResponse(BaseModel):
    media_path: str
    media_url: str
    model: str
    caption: Optional[str] = None


class VoiceGenerateRequest(BaseModel):
    """Generate voice-over from script text."""

    text: str = Field(..., min_length=3, max_length=5000)
    mood: str = Field(default="professional", description="professional|calm|energetic|warm|promo")


class VoiceGenerateResponse(BaseModel):
    media_path: str
    media_url: str
    mood: str
    voice: str
    script_preview: str
