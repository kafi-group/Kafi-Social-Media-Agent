"""
Supported output languages for Prompt Studio (content creation chatbot).

Product catalog names may stay in English; assistant replies are written in the
selected language. Hindi is intentionally excluded from this list.
"""

from __future__ import annotations

from typing import TypedDict


class CreationLanguage(TypedDict):
    code: str
    label: str
    speech_lang: str
    tts_voice: str


DEFAULT_LANGUAGE_CODE = "en"

CREATION_LANGUAGES: list[CreationLanguage] = [
    {"code": "en", "label": "English", "speech_lang": "en-US", "tts_voice": "en-US-GuyNeural"},
    {"code": "ur", "label": "Urdu", "speech_lang": "ur-PK", "tts_voice": "ur-PK-UzmaNeural"},
    {"code": "ar", "label": "Arabic", "speech_lang": "ar-SA", "tts_voice": "ar-SA-ZariyahNeural"},
    {"code": "bn", "label": "Bengali", "speech_lang": "bn-BD", "tts_voice": "bn-BD-NabanitaNeural"},
    {"code": "de", "label": "German", "speech_lang": "de-DE", "tts_voice": "de-DE-KatjaNeural"},
    {"code": "ru", "label": "Russian", "speech_lang": "ru-RU", "tts_voice": "ru-RU-DmitryNeural"},
    {"code": "pt", "label": "Portuguese", "speech_lang": "pt-BR", "tts_voice": "pt-BR-AntonioNeural"},
    {"code": "it", "label": "Italian", "speech_lang": "it-IT", "tts_voice": "it-IT-DiegoNeural"},
    {"code": "tr", "label": "Turkish", "speech_lang": "tr-TR", "tts_voice": "tr-TR-AhmetNeural"},
    {"code": "es", "label": "Spanish", "speech_lang": "es-ES", "tts_voice": "es-ES-AlvaroNeural"},
    {"code": "fr", "label": "French", "speech_lang": "fr-FR", "tts_voice": "fr-FR-DeniseNeural"},
    {"code": "zh", "label": "Chinese (Simplified)", "speech_lang": "zh-CN", "tts_voice": "zh-CN-XiaoxiaoNeural"},
    {"code": "ja", "label": "Japanese", "speech_lang": "ja-JP", "tts_voice": "ja-JP-NanamiNeural"},
    {"code": "ko", "label": "Korean", "speech_lang": "ko-KR", "tts_voice": "ko-KR-SunHiNeural"},
    {"code": "nl", "label": "Dutch", "speech_lang": "nl-NL", "tts_voice": "nl-NL-ColetteNeural"},
    {"code": "pl", "label": "Polish", "speech_lang": "pl-PL", "tts_voice": "pl-PL-MarekNeural"},
    {"code": "id", "label": "Indonesian", "speech_lang": "id-ID", "tts_voice": "id-ID-ArdiNeural"},
    {"code": "ms", "label": "Malay", "speech_lang": "ms-MY", "tts_voice": "ms-MY-OsmanNeural"},
    {"code": "fa", "label": "Persian", "speech_lang": "fa-IR", "tts_voice": "fa-IR-DilaraNeural"},
    {"code": "vi", "label": "Vietnamese", "speech_lang": "vi-VN", "tts_voice": "vi-VN-HoaiMyNeural"},
    {"code": "th", "label": "Thai", "speech_lang": "th-TH", "tts_voice": "th-TH-PremwadeeNeural"},
    {"code": "sw", "label": "Swahili", "speech_lang": "sw-KE", "tts_voice": "sw-KE-ZuriNeural"},
    {"code": "uk", "label": "Ukrainian", "speech_lang": "uk-UA", "tts_voice": "uk-UA-OstapNeural"},
    {"code": "ro", "label": "Romanian", "speech_lang": "ro-RO", "tts_voice": "ro-RO-EmilNeural"},
    {"code": "el", "label": "Greek", "speech_lang": "el-GR", "tts_voice": "el-GR-AthinaNeural"},
]

_LANGUAGE_BY_CODE: dict[str, CreationLanguage] = {lang["code"]: lang for lang in CREATION_LANGUAGES}


def normalize_language_code(code: str | None) -> str:
    """Return a supported language code, defaulting to English."""
    normalized = (code or DEFAULT_LANGUAGE_CODE).strip().lower()
    if normalized in _LANGUAGE_BY_CODE:
        return normalized
    return DEFAULT_LANGUAGE_CODE


def get_language(code: str | None) -> CreationLanguage:
    return _LANGUAGE_BY_CODE[normalize_language_code(code)]


def list_creation_languages() -> list[dict[str, str]]:
    return [
        {
            "code": lang["code"],
            "label": lang["label"],
            "speech_lang": lang["speech_lang"],
        }
        for lang in CREATION_LANGUAGES
    ]
