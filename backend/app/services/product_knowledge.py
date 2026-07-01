"""
Product Knowledge Service
Loads the Kafi Commodities / Essence brand product catalog and provides:
  - product_for_query()       – detect which product a user message is about
  - infer_prompt_media_type()   – guess image vs video from the user's request
  - build_system_prompt()       – system instruction for Prompt Studio chatbot
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, Optional

from app.data.creation_languages import get_language
from app.schemas.creation import CreationIntent

_CATALOG_PATH = Path(__file__).parent.parent / "data" / "kafi_products.json"

# ---------------------------------------------------------------------------
# Load catalog once at import time
# ---------------------------------------------------------------------------

def _load_catalog() -> list[dict]:
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CATALOG: list[dict] = _load_catalog()

# Pre-build alias → product index for O(1) lookup
_ALIAS_INDEX: dict[str, int] = {}
for _idx, _product in enumerate(CATALOG):
    for _alias in _product.get("aliases", []):
        _ALIAS_INDEX[_alias.lower()] = _idx


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def product_for_query(user_message: str) -> Optional[dict]:
    """
    Return the best-matching product dict for the given user message, or None.

    Strategy (fast and reliable):
    1. Normalise the message to lowercase.
    2. Check every alias in the index for substring presence.
    3. Prefer the alias with the most words (most specific match wins).
    """
    text = user_message.lower()
    # remove punctuation for cleaner matching
    text = re.sub(r"[^\w\s]", " ", text)

    best_idx: Optional[int] = None
    best_length: int = 0

    for alias, idx in _ALIAS_INDEX.items():
        if alias in text:
            if len(alias) > best_length:
                best_length = len(alias)
                best_idx = idx

    if best_idx is not None:
        return CATALOG[best_idx]
    return None


def get_all_product_names() -> list[str]:
    """Return a flat list of all product names for display purposes."""
    return [p["name"] for p in CATALOG]


def get_categories() -> list[str]:
    """Return a sorted unique list of product categories."""
    return sorted({p.get("category", "Other") for p in CATALOG})


def infer_prompt_media_type(user_message: str) -> Optional[Literal["image", "video"]]:
    """Infer whether the user wants an image or video prompt from their message."""
    text = user_message.lower()
    video_hints = (
        "video", "reel", "motion", "clip", "animation", "pan ", "rotate",
        "camera move", "15 sec", "30 sec", "commercial", "b-roll",
    )
    image_hints = (
        "image", "photo", "picture", "packshot", "poster", "banner",
        "thumbnail", "still", "hero shot", "product shot", "catalog",
    )
    if any(hint in text for hint in video_hints):
        return "video"
    if any(hint in text for hint in image_hints):
        return "image"
    return None


def _format_product_block(product: dict) -> str:
    packaging_list = "\n".join(f"    • {p}" for p in product.get("packaging", []))
    return (
        f"  Name       : {product['name']}\n"
        f"  Brand      : {product.get('brand', 'Essence')}\n"
        f"  Category   : {product.get('category', '')}\n"
        f"  Description: {product.get('description', '')}\n"
        f"  Packaging  :\n{packaging_list}"
    )


def _reference_image_block() -> str:
    return (
        "═══ REFERENCE IMAGE ATTACHED (vision) ═══\n"
        "The user attached a reference image. You CAN see it in their message.\n\n"
        "YOU MUST:\n"
        "- Analyze the image: product/packaging, label text, colors, lighting, background, "
        "composition, camera angle, props, and overall style.\n"
        "- Write a **Meta AI prompt:** that recreates or adapts that visual for the Essence "
        "product the user names (or ask ONE short question if the target product is unclear).\n"
        "- Ground packaging facts in the catalog when a product is identified.\n"
        "- Output the formatted prompt block only — you are writing a text prompt, NOT generating "
        "a new image yourself.\n\n"
        "YOU MUST NEVER:\n"
        "- Say you cannot see or analyze images.\n"
        "- Ignore the reference image when the user asked you to match or adapt it.\n\n"
    )


def _intent_mode_block(intent: CreationIntent) -> str:
    """Strong mode instructions so the model matches the UI the user selected."""
    if intent == CreationIntent.CREATE_IMAGE:
        return (
            "═══ USER SELECTED MODE: CREATE IMAGE (in-app) ═══\n"
            "The user clicked **Create image**. Your text is NOT shown in the chat — only the "
            "generated image appears. Prompt Studio sends your **Meta AI prompt:** paragraph "
            "directly to the image API.\n\n"
            "YOU MUST:\n"
            "- Output ONLY the **Meta AI prompt:** block (see OUTPUT FORMAT). No intro, no notes.\n"
            "- Write one dense image-generation paragraph grounded in catalog packaging facts.\n\n"
            "YOU MUST NEVER:\n"
            "- Include a **Voice-over script:** or any narration text.\n"
            "- Add chit-chat, apologies, or instructions to copy/paste elsewhere.\n"
            "- Say you cannot generate images.\n\n"
        )
    if intent == CreationIntent.CREATE_VOICE:
        return (
            "═══ USER SELECTED MODE: CREATE VOICE-OVER ═══\n"
            "The user clicked **Create voice**. They will see ONLY your narration script in chat. "
            "They click **Generate voice** separately to hear it — do NOT assume audio is automatic.\n\n"
            "YOU MUST:\n"
            "- Output ONLY the **Voice-over script:** block (2–5 sentences, speakable narration).\n"
            "- Match tone, length, and product facts the user asked for.\n\n"
            "YOU MUST NEVER:\n"
            "- Include a **Meta AI prompt:** or image/visual prompt block.\n"
            "- Redirect to ElevenLabs or external TTS tools.\n\n"
        )
    return (
        "═══ USER SELECTED MODE: WRITE PROMPT ═══\n"
        "The user wants a copy-paste prompt for Meta AI, Google Flow, or similar tools.\n"
        "Output ONLY the formatted prompt block — no voice-over script, no in-app generation.\n"
        "For video/reel requests set **Type:** Video and describe motion and pacing.\n\n"
    )


def _output_format_block(intent: CreationIntent) -> str:
    """Intent-specific output structure — one output type per mode."""
    if intent == CreationIntent.CREATE_IMAGE:
        return (
            "OUTPUT FORMAT (strict — nothing else):\n"
            "---\n"
            "**Meta AI prompt:**\n"
            "[One dense paragraph for image generation. No bullet lists inside this block.]\n"
            "---\n"
        )
    if intent == CreationIntent.CREATE_VOICE:
        return (
            "OUTPUT FORMAT (strict — nothing else):\n"
            "---\n"
            "**Voice-over script:**\n"
            "[2–5 sentences of speakable narration. No stage directions unless brief.]\n"
            "---\n"
        )
    return (
        "OUTPUT FORMAT:\n"
        "---\n"
        "**Product:** [full catalog name]\n"
        "**Type:** Image | Video\n"
        "**Use case:** [e.g. Instagram feed, Amazon listing, 15s reel]\n"
        "**Meta AI prompt:**\n"
        "[One dense paragraph — copy/paste ready. No bullet lists inside this block.]\n"
        "**Notes:** [optional, one line max]\n"
        "---\n"
        "Do NOT include **Voice-over script:** in this mode.\n"
    )


def _language_block(language_code: str) -> str:
    lang = get_language(language_code)
    return (
        f"═══ RESPONSE LANGUAGE: {lang['label']} ({lang['code']}) ═══\n"
        f"Write ALL assistant text in {lang['label']}.\n"
        "- User messages may be in any language; still reply in "
        f"{lang['label']} unless they explicitly ask for another language.\n"
        "- Keep brand names (Essence, Kafi) and official catalog product names "
        "accurate — use English catalog names when no established translation exists.\n"
        "- Section headers like **Meta AI prompt:** and **Voice-over script:** stay "
        "in English for tool compatibility; the content inside each block must be "
        f"in {lang['label']}.\n"
        "- For RTL languages (Arabic, Urdu, Persian), write naturally in that script.\n\n"
    )


def build_system_prompt(
    matched_product: Optional[dict] = None,
    media_type: Optional[Literal["image", "video"]] = None,
    intent: CreationIntent = CreationIntent.PROMPT,
    has_reference_image: bool = False,
    language: str = "en",
) -> str:
    """
    Build the system prompt for the Content Creation chatbot.
    """
    reference_block = _reference_image_block() if has_reference_image else ""

    media_focus = ""
    if intent == CreationIntent.CREATE_IMAGE or media_type == "image":
        media_focus = (
            "Focus: single still frame / packshot / marketing visual for in-app image generation.\n"
        )
    elif media_type == "video":
        media_focus = (
            "Focus: video prompt — motion, pacing, camera movement, opening/closing frames "
            "for Meta AI or Google Flow.\n"
        )
    elif intent == CreationIntent.CREATE_VOICE:
        media_focus = "Focus: spoken voice-over / narration script for product marketing.\n"

    base = (
        "You are the Prompt Studio creative assistant for Kafi Commodities (Pvt) Ltd — "
        "the Pakistani export company behind the **Essence** brand.\n\n"
        f"{_language_block(language)}"
        f"{reference_block}"
        f"{_intent_mode_block(intent)}"
        f"{media_focus}"
        "BRAND & VISUAL DIRECTION (Essence):\n"
        "- Premium export-quality food packaging; clean, appetizing, trustworthy.\n"
        "- Typical formats: PET bottles, glass jars, pouches, master cartons — use ONLY what "
        "appears in the product's packaging list.\n"
        "- Label should read **Essence** (or Essence sub-brand styling); South Asian / Pakistani "
        "heritage cues where appropriate without stereotypes.\n"
        "- Commercial photography / ad aesthetic: sharp focus, realistic materials, no cartoon style "
        "unless the user explicitly asks.\n\n"
        "PROMPT ENGINEERING RULES:\n"
        "1. Ground every prompt in the real product name, category, and packaging from the catalog.\n"
        "2. Be visually specific: subject, packaging size/type, label, ingredients texture, "
        "lighting (e.g. soft studio key light), background, camera angle, lens feel, color mood, "
        "aspect ratio if relevant (1:1 feed, 4:5, 9:16 reel).\n"
        "3. For VIDEO prompts add: duration feel (e.g. 10–15s), motion (slow pan, pour, steam), "
        "scene beats (opening → hero → CTA), and audio mood if helpful (no copyrighted music names).\n"
        "4. Do NOT invent SKUs, weights, or pack types that are not in the catalog.\n"
        "5. Do NOT write long product brochures — only include catalog facts that improve the visual prompt.\n"
        "6. If the user asks for variations, give 2–3 clearly labelled options (Option A, B, C).\n"
        "7. If the product is ambiguous, ask ONE short clarifying question before writing prompts.\n"
        "8. If no specific product is named, use the catalog overview and ask which product/format "
        "they need — or draft a category-level prompt and note what to specify.\n\n"
        f"{_output_format_block(intent)}\n"
        "Keep chatter outside the block minimal. Lead with the formatted block.\n\n"
    )

    if matched_product:
        product_block = (
            "TARGET PRODUCT (catalog ground truth — use accurately):\n"
            f"{_format_product_block(matched_product)}\n\n"
            "Reflect the correct packaging line (PET vs glass, size) from the list above."
        )
        return base + product_block

    categories = get_categories()
    cat_list = "\n".join(f"  • {c}" for c in categories)
    catalog_summary = (
        "PRODUCT CATALOG OVERVIEW — Essence brand categories:\n"
        f"{cat_list}\n\n"
        "No single product was detected in the user's message. Ask which product and packaging "
        "format they need, or produce a category-level prompt and state assumptions clearly."
    )
    return base + catalog_summary
