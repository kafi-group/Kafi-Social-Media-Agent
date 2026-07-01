export interface CreationLanguageOption {
  code: string;
  label: string;
  speech_lang: string;
}

export const DEFAULT_CREATION_LANGUAGE = 'en';

/** Fallback when /creation/models has not loaded yet (must match backend list). */
export const FALLBACK_CREATION_LANGUAGES: CreationLanguageOption[] = [
  { code: 'en', label: 'English', speech_lang: 'en-US' },
  { code: 'ur', label: 'Urdu', speech_lang: 'ur-PK' },
  { code: 'ar', label: 'Arabic', speech_lang: 'ar-SA' },
  { code: 'bn', label: 'Bengali', speech_lang: 'bn-BD' },
  { code: 'de', label: 'German', speech_lang: 'de-DE' },
  { code: 'ru', label: 'Russian', speech_lang: 'ru-RU' },
  { code: 'pt', label: 'Portuguese', speech_lang: 'pt-BR' },
  { code: 'it', label: 'Italian', speech_lang: 'it-IT' },
  { code: 'tr', label: 'Turkish', speech_lang: 'tr-TR' },
  { code: 'es', label: 'Spanish', speech_lang: 'es-ES' },
  { code: 'fr', label: 'French', speech_lang: 'fr-FR' },
  { code: 'zh', label: 'Chinese (Simplified)', speech_lang: 'zh-CN' },
  { code: 'ja', label: 'Japanese', speech_lang: 'ja-JP' },
  { code: 'ko', label: 'Korean', speech_lang: 'ko-KR' },
  { code: 'nl', label: 'Dutch', speech_lang: 'nl-NL' },
  { code: 'pl', label: 'Polish', speech_lang: 'pl-PL' },
  { code: 'id', label: 'Indonesian', speech_lang: 'id-ID' },
  { code: 'ms', label: 'Malay', speech_lang: 'ms-MY' },
  { code: 'fa', label: 'Persian', speech_lang: 'fa-IR' },
  { code: 'vi', label: 'Vietnamese', speech_lang: 'vi-VN' },
  { code: 'th', label: 'Thai', speech_lang: 'th-TH' },
  { code: 'sw', label: 'Swahili', speech_lang: 'sw-KE' },
  { code: 'uk', label: 'Ukrainian', speech_lang: 'uk-UA' },
  { code: 'ro', label: 'Romanian', speech_lang: 'ro-RO' },
  { code: 'el', label: 'Greek', speech_lang: 'el-GR' },
];

const STORAGE_KEY = 'creationLanguage';

export function readStoredCreationLanguage(): string {
  if (typeof window === 'undefined') return DEFAULT_CREATION_LANGUAGE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored && FALLBACK_CREATION_LANGUAGES.some((lang) => lang.code === stored)) {
    return stored;
  }
  return DEFAULT_CREATION_LANGUAGE;
}

export function storeCreationLanguage(code: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, code);
}

export function speechLangForCode(
  languages: CreationLanguageOption[],
  code: string
): string {
  return (
    languages.find((lang) => lang.code === code)?.speech_lang ??
    FALLBACK_CREATION_LANGUAGES.find((lang) => lang.code === code)?.speech_lang ??
    'en-US'
  );
}
