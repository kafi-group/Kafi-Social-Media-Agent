export interface SavedCreationPrompt {
  text: string;
  savedAt: string;
}

const STORAGE_KEY = 'creationSavedPrompt';
const LEGACY_STORAGE_KEY = 'creationSavedPrompts';

function migrateLegacyPrompt(): SavedCreationPrompt | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, SavedCreationPrompt>;
    if (!parsed || typeof parsed !== 'object') return null;

    let best: SavedCreationPrompt | null = null;
    for (const entry of Object.values(parsed)) {
      if (!entry?.text?.trim()) continue;
      if (!best || entry.savedAt > best.savedAt) {
        best = entry;
      }
    }
    if (best) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(best));
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
    return best;
  } catch {
    return null;
  }
}

/** One shared prompt (text only) — reusable in Create image, Create voice, and Write prompt. */
export function readSavedCreationPrompt(): SavedCreationPrompt | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as SavedCreationPrompt;
      if (parsed?.text?.trim()) return parsed;
    }
    return migrateLegacyPrompt();
  } catch {
    return null;
  }
}

export function saveCreationPrompt(text: string): SavedCreationPrompt {
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error('Nothing to save');
  }
  const entry: SavedCreationPrompt = {
    text: trimmed,
    savedAt: new Date().toISOString(),
  };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entry));
  }
  return entry;
}

export function clearSavedCreationPrompt(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
}

export function previewSavedPrompt(text: string, maxLength = 120): string {
  const singleLine = text.replace(/\s+/g, ' ').trim();
  if (singleLine.length <= maxLength) return singleLine;
  return `${singleLine.slice(0, maxLength)}…`;
}
