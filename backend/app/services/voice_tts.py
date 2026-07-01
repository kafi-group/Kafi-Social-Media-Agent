"""
Voice-over generation via edge-tts (free, no API key).

Different moods map to voice + rate/pitch presets.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Literal

import edge_tts

from app.data.creation_languages import get_language
from app.services.media import MediaService
from app.utils.exceptions import ContentGenerationError
from app.utils.logger import logger

VoiceMood = Literal["professional", "calm", "energetic", "warm", "promo"]

MOOD_PRESETS: dict[VoiceMood, dict[str, str]] = {
    "professional": {
        "voice": "en-US-GuyNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "label": "Professional",
    },
    "calm": {
        "voice": "en-US-AriaNeural",
        "rate": "-12%",
        "pitch": "-2Hz",
        "label": "Calm & soothing",
    },
    "energetic": {
        "voice": "en-US-JennyNeural",
        "rate": "+18%",
        "pitch": "+4Hz",
        "label": "Energetic",
    },
    "warm": {
        "voice": "en-GB-SoniaNeural",
        "rate": "-5%",
        "pitch": "-1Hz",
        "label": "Warm & friendly",
    },
    "promo": {
        "voice": "en-US-DavisNeural",
        "rate": "+22%",
        "pitch": "+3Hz",
        "label": "Promo / sales",
    },
}


def list_voice_moods() -> list[dict[str, str]]:
    return [{"id": mood, "label": preset["label"]} for mood, preset in MOOD_PRESETS.items()]


def extract_voice_script(text: str) -> str:
    """Use narration-friendly text from an assistant reply."""
    if not text.strip():
        raise ContentGenerationError("No script text provided.")

    patterns = [
        r"\*\*Voice-over script:\*\*\s*\n([\s\S]*?)(?=\n\*\*|\n---|\Z)",
        r"\*\*Voice[/-]?over script:\*\*\s*\n([\s\S]*?)(?=\n\*\*|\n---|\Z)",
        r"\*\*Narration:\*\*\s*\n([\s\S]*?)(?=\n\*\*|\n---|\Z)",
        r"\*\*Script:\*\*\s*\n([\s\S]*?)(?=\n\*\*|\n---|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            script = match.group(1).strip()
            if script:
                return script[:5000]

    # Strip markdown formatting for a readable default script
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"^---\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    if len(cleaned) > 5000:
        cleaned = cleaned[:5000]
    return cleaned


async def _synthesize_to_bytes(text: str, mood: VoiceMood, language: str = "en") -> bytes:
    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["professional"])
    lang = get_language(language)
    voice = lang["tts_voice"]
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=preset["rate"],
        pitch=preset["pitch"],
    )

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await communicate.save(str(tmp_path))
        data = tmp_path.read_bytes()
        if not data:
            raise ContentGenerationError("Voice synthesis returned empty audio.")
        return data
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


async def generate_voice_async(
    text: str,
    mood: VoiceMood = "professional",
    language: str = "en",
) -> dict:
    """Generate MP3 voice-over and store via MediaService."""
    script = extract_voice_script(text)
    if len(script.strip()) < 3:
        raise ContentGenerationError("Script is too short for voice generation.")

    lang = get_language(language)
    logger.info(
        f"Generating voice-over (mood={mood}, language={lang['code']}, chars={len(script)})"
    )

    try:
        audio_bytes = await _synthesize_to_bytes(script, mood, language=lang["code"])
    except Exception as exc:
        raise ContentGenerationError(
            f"Voice generation failed. If this repeats, wait a few seconds and retry. ({exc})"
        ) from exc

    media_service = MediaService()
    stored = media_service.save_bytes(
        audio_bytes,
        extension=".mp3",
        media_type="audio",
        original_name=f"voiceover-{mood}.mp3",
        validate=False,
    )

    return {
        "media_path": stored["media_path"],
        "media_url": stored["media_url"],
        "mood": mood,
        "voice": lang["tts_voice"],
        "script_preview": script[:200] + ("…" if len(script) > 200 else ""),
    }
