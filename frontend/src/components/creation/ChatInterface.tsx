'use client';

import React, { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Send,
  Copy,
  Check,
  Loader2,
  Bot,
  User,
  Trash2,
  Mic,
  Sparkles,
  ImageIcon,
  Clapperboard,
  Paperclip,
  X,
  Bookmark,
  BookmarkCheck,
} from 'lucide-react';
import { API_ENDPOINTS, API_CONFIG, apiFetch, fetchWithTimeout } from '@/lib/api-client';
import {
  FALLBACK_CREATION_LANGUAGES,
  readStoredCreationLanguage,
  speechLangForCode,
  storeCreationLanguage,
  type CreationLanguageOption,
} from '@/lib/creation-languages';
import {
  clearSavedCreationPrompt,
  previewSavedPrompt,
  readSavedCreationPrompt,
  saveCreationPrompt,
  type SavedCreationPrompt,
} from '@/lib/creation-saved-prompts';
import { useSpeechToText } from '@/hooks/useSpeechToText';
import type {
  ChatMessage,
  ChatResponse,
  CreationIntent,
  CreationModelsResponse,
  ImageGenerateResponse,
  VoiceGenerateResponse,
} from '@/lib/types';

const CREATION_MODES: {
  id: CreationIntent;
  label: string;
  icon: typeof ImageIcon;
  description: string;
  placeholder: string;
}[] = [
  {
    id: 'create_image',
    label: 'Create image',
    icon: ImageIcon,
    description: 'Generate a product image in-app — no prompt text shown',
    placeholder:
      'Describe the shot — e.g. Essence mango pickle 330g glass jar, studio packshot, white background, Instagram feed…',
  },
  {
    id: 'create_voice',
    label: 'Create voice',
    icon: Mic,
    description: 'Write a voice-over script — click Generate voice when ready',
    placeholder:
      'Describe the voice-over — e.g. 20s promo for Himalayan pink salt, warm and trustworthy tone…',
  },
  {
    id: 'prompt',
    label: 'Write prompt',
    icon: Sparkles,
    description: 'Copy-paste prompt for Meta AI or Google Flow — text only',
    placeholder:
      'Ask for a prompt — product, packaging, platform, mood, image or video…',
  },
];

const GEMINI_WEB_FALLBACK_URL = 'https://gemini.google.com/app';
const GOOGLE_FLOW_FALLBACK_URL = 'https://labs.google/fx/tools/flow';

const MAX_REFERENCE_IMAGE_BYTES = 4 * 1024 * 1024;
const MAX_REFERENCE_IMAGES = 5;
const ALLOWED_REFERENCE_IMAGE_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
]);

interface PendingAttachment {
  id: string;
  previewUrl: string;
  base64: string;
  mimeType: string;
  name: string;
}

function stripDataUrlPrefix(dataUrl: string): string {
  const comma = dataUrl.indexOf(',');
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

function readImageFile(
  file: File
): Promise<{ base64: string; previewUrl: string; mimeType: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve({
        base64: stripDataUrlPrefix(result),
        previewUrl: result,
        mimeType: file.type,
      });
    };
    reader.onerror = () => reject(new Error('Could not read image'));
    reader.readAsDataURL(file);
  });
}

function toApiMessages(messages: ExtendedChatMessage[]): ChatMessage[] {
  // Keep full text history for session memory, but only re-send image bytes
  // for the latest attachment turn (keeps payload small while preserving product context).
  let lastImageIndex = -1;
  messages.forEach((m, i) => {
    if ((m.images && m.images.length > 0) || m.image_base64) {
      lastImageIndex = i;
    }
  });

  return messages.map((m, i) => {
    const entry: ChatMessage = { role: m.role, content: m.content };
    const imageCount = m.images?.length
      ? m.images.length
      : m.image_base64
        ? 1
        : 0;

    if (imageCount > 0 && i === lastImageIndex) {
      if (m.images?.length) {
        entry.images = m.images.map((img) => ({
          image_base64: img.image_base64,
          image_mime_type: img.image_mime_type ?? 'image/jpeg',
        }));
      } else if (m.image_base64) {
        entry.image_base64 = m.image_base64;
        entry.image_mime_type = m.image_mime_type ?? 'image/jpeg';
      }
    } else if (imageCount > 0) {
      entry.content = [
        m.content.trim(),
        `[Earlier in this chat the user attached ${imageCount} reference image${
          imageCount === 1 ? '' : 's'
        }. Keep using that product/visual context for follow-ups.]`,
      ]
        .filter(Boolean)
        .join('\n\n');
    }
    return entry;
  });
}

// ---------------------------------------------------------------------------
// Extended message type
// ---------------------------------------------------------------------------

interface ExtendedChatMessage extends ChatMessage {
  generatedImageUrl?: string | null;
  generatedImageProvider?: string | null;
  generatedImageModel?: string | null;
  generatedImageFallbackReason?: string | null;
  generatedAudioUrl?: string | null;
  imageGenerationError?: string | null;
  intent?: CreationIntent;
}

// ---------------------------------------------------------------------------
// Main ChatInterface
// ---------------------------------------------------------------------------

export default function ChatInterface() {
  const [modelLabel, setModelLabel] = useState<string>('Loading…');
  const [geminiWebUrl, setGeminiWebUrl] = useState<string>(GEMINI_WEB_FALLBACK_URL);
  const [googleFlowUrl, setGoogleFlowUrl] = useState<string>(GOOGLE_FLOW_FALLBACK_URL);
  const [chatReady, setChatReady] = useState<boolean>(true);
  const [imageReady, setImageReady] = useState<boolean>(false);
  const [imageModelLabel, setImageModelLabel] = useState<string>('');
  const [voiceMoods, setVoiceMoods] = useState<{ id: string; label: string }[]>([]);
  const [voiceMood, setVoiceMood] = useState<string>('professional');
  const [creationLanguage, setCreationLanguage] = useState<string>(() => readStoredCreationLanguage());
  const [languageOptions, setLanguageOptions] = useState<CreationLanguageOption[]>(
    FALLBACK_CREATION_LANGUAGES
  );
  const [creationIntent, setCreationIntent] = useState<CreationIntent>('create_image');

  const activeMode =
    CREATION_MODES.find((m) => m.id === creationIntent) ?? CREATION_MODES[0];

  const [messages, setMessages] = useState<ExtendedChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [generatingImageIndex, setGeneratingImageIndex] = useState<number | null>(null);
  const [generatingVoiceIndex, setGeneratingVoiceIndex] = useState<number | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [savedPrompt, setSavedPrompt] = useState<SavedCreationPrompt | null>(() =>
    typeof window !== 'undefined' ? readSavedCreationPrompt() : null
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const speechLang = speechLangForCode(languageOptions, creationLanguage);

  const appendFinalTranscript = React.useCallback((text: string) => {
    setInput((prev) => {
      const base = prev.trimEnd();
      const addition = text.trim();
      if (!addition) return prev;
      return base ? `${base} ${addition}` : addition;
    });
  }, []);

  const {
    isListening,
    isSupported: speechSupported,
    toggleListening,
    stopListening: stopSpeechListening,
  } = useSpeechToText({
    lang: speechLang,
    onFinalTranscript: appendFinalTranscript,
    onError: (message) => toast.error(message),
  });

  useEffect(() => {
    if (sending && isListening) {
      stopSpeechListening();
    }
  }, [sending, isListening, stopSpeechListening]);

  const refreshCreationCapabilities = React.useCallback(async (): Promise<{
    imageReady: boolean;
    imageModel: string;
  }> => {
    try {
      const res = await fetchWithTimeout(API_ENDPOINTS.CREATION_MODELS);
      if (!res.ok) throw new Error('Failed to load models');
      const data: CreationModelsResponse = await res.json();
      setModelLabel(data.models[0]?.label ?? 'AI Assistant');
      setGeminiWebUrl(data.gemini_web_url || GEMINI_WEB_FALLBACK_URL);
      setGoogleFlowUrl(GOOGLE_FLOW_FALLBACK_URL);
      setChatReady(data.chat_ready);
      const ready = Boolean(data.image_ready);
      const imageModel = data.image_model ?? '';
      setImageReady(ready);
      setImageModelLabel(imageModel);
      setVoiceMoods(data.voice_moods ?? []);
      if (data.languages?.length) {
        setLanguageOptions(data.languages);
      }
      return { imageReady: ready, imageModel };
    } catch {
      return { imageReady: false, imageModel: '' };
    }
  }, []);

  const imageNotReadyMessage = (imageModel: string) => {
    const backend = API_CONFIG.baseURL;
    if (imageModel) {
      return `Image API not ready (${imageModel}). Backend: ${backend}`;
    }
    return (
      `Image API not ready on ${backend}. ` +
      'Hard-refresh (Ctrl+Shift+R), confirm Vercel NEXT_PUBLIC_API_URL is ' +
      'https://kafi-social-media-agent.up.railway.app, then redeploy Vercel.'
    );
  };

  useEffect(() => {
    void refreshCreationCapabilities().catch(() => {
      toast.error('Could not load AI models. Is the backend running?');
    });
  }, [refreshCreationCapabilities]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const sendMessage = async () => {
    const text = input.trim();
    const hasAttachment = pendingAttachments.length > 0;
    if ((!text && !hasAttachment) || sending) return;

    if (!chatReady) {
      toast.error(
        'Chat is not configured. Add CREATION_GEMINI_API_KEY in the backend .env (2nd free key from aistudio.google.com/apikey).'
      );
      return;
    }

    const userMsg: ExtendedChatMessage = {
      role: 'user',
      content:
        text ||
        (pendingAttachments.length > 1
          ? `Analyze all ${pendingAttachments.length} attached reference images carefully and write a detailed marketing prompt that matches their combined style and my request.`
          : 'Analyze the attached reference image carefully and write a detailed marketing prompt that matches its style and my request.'),
      ...(pendingAttachments.length
        ? {
            images: pendingAttachments.map((a) => ({
              image_base64: a.base64,
              image_mime_type: a.mimeType,
              image_preview_url: a.previewUrl,
            })),
          }
        : {}),
    };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setPendingAttachments([]);
    setSending(true);

    try {
      const res = await apiFetch(API_ENDPOINTS.CREATION_CHAT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: '',
          intent: creationIntent,
          language: creationLanguage,
          messages: toApiMessages(nextMessages),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Chat request failed');
      }
      const data: ChatResponse = await res.json();
      const assistantMsg: ExtendedChatMessage = {
        role: 'assistant',
        content: data.reply,
        intent: creationIntent,
      };
      const assistantIndex = nextMessages.length;
      setMessages((prev) => [...prev, assistantMsg]);

      if (creationIntent === 'create_image') {
        const { imageReady: ready, imageModel } = await refreshCreationCapabilities();
        if (ready) {
          void runGenerateImage(assistantIndex, data.reply);
        } else {
          const configMsg = imageNotReadyMessage(imageModel);
          setMessages((prev) =>
            prev.map((m, i) =>
              i === assistantIndex ? { ...m, imageGenerationError: configMsg } : m
            )
          );
          toast.error(configMsg);
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Chat request failed';
      toast.error(msg);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Sorry, something went wrong: ${msg}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const startNewChat = () => {
    if (sending) return;
    setMessages([]);
    setPendingAttachments([]);
    setInput('');
    setCopiedIndex(null);
    setGeneratingImageIndex(null);
    setGeneratingVoiceIndex(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    toast.success('Started a new chat — previous memory cleared.');
  };

  const openGeminiWeb = () => {
    window.open(geminiWebUrl, '_blank', 'noopener,noreferrer');
  };

  const openFlowAI = () => {
    window.open(googleFlowUrl, '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    setSavedPrompt(readSavedCreationPrompt());
  }, []);

  const handleSavePrompt = (text: string) => {
    try {
      const entry = saveCreationPrompt(text);
      setSavedPrompt(entry);
      toast.success('Prompt saved (text only) — reuse in Create image or Create voice');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save prompt');
    }
  };

  const handleUseSavedPrompt = () => {
    if (!savedPrompt?.text?.trim()) {
      toast.error('No saved prompt yet — save prompt text from an assistant reply first');
      return;
    }
    setInput(savedPrompt.text);
    toast.success('Loaded saved prompt into the box — send when ready');
  };

  const handleClearSavedPrompt = () => {
    clearSavedCreationPrompt();
    setSavedPrompt(null);
    toast.success('Cleared saved prompt');
  };

  const runGenerateImage = async (index: number, promptText: string) => {
    const { imageReady: ready, imageModel } = await refreshCreationCapabilities();
    if (!ready) {
      const configMsg = imageNotReadyMessage(imageModel);
      toast.error(configMsg);
      setMessages((prev) =>
        prev.map((m, i) => (i === index ? { ...m, imageGenerationError: configMsg } : m))
      );
      return;
    }

    setGeneratingImageIndex(index);
    try {
      const res = await apiFetch(API_ENDPOINTS.CREATION_GENERATE_IMAGE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText }),
        signal: AbortSignal.timeout(API_CONFIG.timeout),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'Image generation failed');
      }
      const data: ImageGenerateResponse = await res.json();
      if (!data.media_url) {
        throw new Error('Image API returned no media URL');
      }
      setMessages((prev) =>
        prev.map((m, i) =>
          i === index
            ? {
                ...m,
                generatedImageUrl: data.media_url,
                generatedImageProvider: data.provider || null,
                generatedImageModel: data.model || null,
                generatedImageFallbackReason: data.fallback_reason || null,
                imageGenerationError: null,
              }
            : m
        )
      );
      if (data.provider === 'gemini') {
        toast.success('Image generated by Gemini');
      } else if (data.provider === 'cloudflare') {
        toast.success(
          data.fallback_reason
            ? 'Gemini unavailable — image generated by Cloudflare Flux'
            : 'Image generated by Cloudflare Flux'
        );
      } else if (data.provider === 'modelslab') {
        toast.success('Image generated by ModelsLab');
      } else {
        toast.success('Image generated in-app');
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Image generation failed';
      setMessages((prev) =>
        prev.map((m, i) => (i === index ? { ...m, imageGenerationError: message } : m))
      );
      toast.error(message);
    } finally {
      setGeneratingImageIndex(null);
    }
  };

  const runGenerateVoice = async (index: number, scriptText: string) => {
    setGeneratingVoiceIndex(index);
    try {
      const res = await apiFetch(API_ENDPOINTS.CREATION_GENERATE_VOICE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: scriptText, mood: voiceMood, language: creationLanguage }),
        signal: AbortSignal.timeout(API_CONFIG.timeout),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === 'string' ? err.detail : 'Voice generation failed');
      }
      const data: VoiceGenerateResponse = await res.json();
      setMessages((prev) =>
        prev.map((m, i) =>
          i === index ? { ...m, generatedAudioUrl: data.media_url } : m
        )
      );
      toast.success('Voice-over generated in-app');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Voice generation failed');
    } finally {
      setGeneratingVoiceIndex(null);
    }
  };

  const generateImage = async (index: number) => {
    const msg = messages[index];
    if (!msg || msg.role !== 'assistant') return;
    await runGenerateImage(index, msg.content);
  };

  const generateVoice = async (index: number) => {
    const msg = messages[index];
    if (!msg || msg.role !== 'assistant') return;
    await runGenerateVoice(index, msg.content);
  };

  const copyMessage = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopiedIndex(null), 1500);
    } catch {
      toast.error('Could not copy');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearPendingAttachments = () => {
    setPendingAttachments([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removePendingAttachment = (id: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id));
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleImageFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;

    const remainingSlots = MAX_REFERENCE_IMAGES - pendingAttachments.length;
    if (remainingSlots <= 0) {
      toast.error(`You can attach up to ${MAX_REFERENCE_IMAGES} images.`);
      e.target.value = '';
      return;
    }

    const selected = files.slice(0, remainingSlots);
    if (files.length > remainingSlots) {
      toast.error(`Only ${MAX_REFERENCE_IMAGES} images allowed — added the first ${remainingSlots}.`);
    }

    const accepted: PendingAttachment[] = [];
    for (const file of selected) {
      if (!ALLOWED_REFERENCE_IMAGE_TYPES.has(file.type)) {
        toast.error(`${file.name}: use JPEG, PNG, WebP, or GIF.`);
        continue;
      }
      if (file.size > MAX_REFERENCE_IMAGE_BYTES) {
        toast.error(`${file.name}: must be under 4 MB.`);
        continue;
      }
      try {
        const { base64, previewUrl, mimeType } = await readImageFile(file);
        accepted.push({
          id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
          base64,
          previewUrl,
          mimeType,
          name: file.name,
        });
      } catch {
        toast.error(`Could not read ${file.name}.`);
      }
    }

    if (accepted.length) {
      setPendingAttachments((prev) => [...prev, ...accepted].slice(0, MAX_REFERENCE_IMAGES));
    }
    e.target.value = '';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[70vh] dark:bg-slate-800 dark:border-slate-600">
      {/* Toolbar */}
      <div className="flex flex-nowrap items-center gap-2 p-4 border-b border-slate-200 overflow-x-auto dark:border-slate-600">
        <span className="text-sm text-slate-600 bg-slate-100 rounded-lg px-3 py-1.5 shrink-0 dark:bg-slate-700 dark:text-slate-200">
          {modelLabel}
        </span>
        <select
          value={creationLanguage}
          onChange={(e) => {
            const next = e.target.value;
            setCreationLanguage(next);
            storeCreationLanguage(next);
          }}
          className="shrink-0 text-sm rounded-lg border border-brand-200 bg-white px-2 py-1.5 text-brand-800 dark:bg-slate-700 dark:border-slate-500 dark:text-slate-100"
          title="Language for chat replies and voice-over"
        >
          {languageOptions.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
        {imageModelLabel ? (
          <span className="text-xs text-slate-500 bg-slate-50 rounded-lg px-2 py-1 shrink-0 dark:bg-slate-700/60 dark:text-slate-300">
            Images: {imageModelLabel}
          </span>
        ) : null}

        <div className="flex-1 min-w-2" />

        {voiceMoods.length > 0 && (
          <select
            value={voiceMood}
            onChange={(e) => setVoiceMood(e.target.value)}
            className="shrink-0 text-sm rounded-lg border border-brand-200 bg-white px-2 py-1.5 text-brand-800 dark:bg-slate-700 dark:border-slate-500 dark:text-slate-100"
            title="Voice-over mood for in-app generation"
          >
            {voiceMoods.map((m) => (
              <option key={m.id} value={m.id}>
                Voice: {m.label}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          onClick={openGeminiWeb}
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors dark:text-gold-300 dark:hover:text-gold-200 dark:border-slate-500 dark:hover:bg-slate-700"
          title="Open Google Gemini to create images"
        >
          <ImageIcon className="w-4 h-4" />
          Gemini Image Creation
        </button>
        <button
          type="button"
          onClick={openFlowAI}
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors dark:text-gold-300 dark:hover:text-gold-200 dark:border-slate-500 dark:hover:bg-slate-700"
          title="Open Google Flow for AI video creation"
        >
          <Clapperboard className="w-4 h-4" />
          Flow AI Video Creation
        </button>

        {messages.length > 0 && (
          <button
            onClick={startNewChat}
            className="inline-flex shrink-0 items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors"
            title="End this chat and start fresh (clears conversation memory)"
          >
            <Trash2 className="w-4 h-4" />
            New chat
          </button>
        )}
      </div>

      {savedPrompt ? (
        <div className="mx-4 mt-4 rounded-lg border border-emerald-200 bg-emerald-50/80 px-3 py-2.5 dark:border-emerald-800/60 dark:bg-emerald-950/30">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-emerald-900 dark:text-emerald-200 flex items-center gap-1.5">
                <BookmarkCheck className="w-3.5 h-3.5" />
                Saved prompt (text only)
              </p>
              <p className="text-[11px] text-emerald-800/80 dark:text-emerald-100/70 mt-0.5">
                Reuse in Create image, Create voice, or Write prompt — not images or audio files.
              </p>
              <p className="text-xs text-emerald-800/90 dark:text-emerald-100/80 mt-1 line-clamp-2">
                {previewSavedPrompt(savedPrompt.text)}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-1.5">
              <button
                type="button"
                onClick={handleUseSavedPrompt}
                className="text-xs font-medium rounded-md px-2.5 py-1 border border-emerald-300 text-emerald-900 hover:bg-emerald-100 dark:border-emerald-700 dark:text-emerald-100 dark:hover:bg-emerald-900/40"
              >
                Use saved prompt
              </button>
              <button
                type="button"
                onClick={handleClearSavedPrompt}
                className="text-xs text-emerald-800/80 hover:text-red-700 dark:text-emerald-200/80 dark:hover:text-red-300 px-2 py-1"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
            <Bot className="w-12 h-12 mb-3 text-slate-300" />
            <p className="text-sm max-w-md mb-4">
              Select a mode below — <strong>Create image</strong> generates visuals in-app,{' '}
              <strong>Create voice</strong> writes a script you can turn into audio, and{' '}
              <strong>Write prompt</strong> gives copy-paste text for Meta AI or Flow. Choose a{' '}
              <strong>language</strong> in the toolbar for replies in English, Urdu, Arabic, and more.
              This chat remembers your product details until you click <strong>New chat</strong>.
              <strong> Save prompt</strong> stores one text prompt in your browser (not images or voice files)
              — reuse it in <strong>Create image</strong> or <strong>Create voice</strong> anytime.
            </p>
            {/* Quick-start suggestions */}
            <div className="flex flex-wrap justify-center gap-2 text-xs">
              {[
                'Essence mango pickle 330g glass jar — studio packshot for Instagram',
                'Himalayan pink salt pouch — lifestyle kitchen scene',
                'Garlic paste 1kg PET bottle — Amazon listing white background',
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => {
                    setCreationIntent('create_image');
                    setInput(q);
                  }}
                  className="px-3 py-1.5 rounded-full border border-slate-200 hover:border-brand-300 hover:text-brand-700 hover:bg-brand-50 transition-colors dark:border-slate-600 dark:hover:border-brand-500 dark:hover:text-gold-300"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          const msgIntent = msg.intent ?? 'prompt';
          const showTextBubble = isUser || msgIntent !== 'create_image';
          return (
            <div key={index} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
              {!isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center dark:bg-brand-900/60">
                  <Bot className="w-4 h-4 text-brand-700 dark:text-gold-300" />
                </div>
              )}

              <div className={`max-w-[75%] space-y-2 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
                {!isUser && generatingImageIndex === index && (
                  <div className="text-xs text-brand-700 dark:text-gold-300 flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Generating image in-app…
                  </div>
                )}
                {!isUser && generatingVoiceIndex === index && (
                  <div className="text-xs text-brand-700 dark:text-gold-300 flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Generating voice-over…
                  </div>
                )}

                {/* Generated media previews */}
                {!isUser && msg.imageGenerationError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 max-w-sm dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
                    {msg.imageGenerationError}
                  </div>
                )}
                {!isUser && msg.generatedImageUrl && (
                  <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-600 max-w-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={msg.generatedImageUrl}
                      alt="Generated product visual"
                      className="w-full h-auto object-contain bg-white dark:bg-slate-900"
                      onError={() => {
                        setMessages((prev) =>
                          prev.map((m, i) =>
                            i === index
                              ? {
                                  ...m,
                                  imageGenerationError:
                                    'Image was generated but could not load in the browser. Check Supabase bucket is public or use HTTPS media URLs.',
                                }
                              : m
                          )
                        );
                      }}
                    />
                    <div className="px-3 py-2 bg-slate-50 border-t border-slate-200 dark:bg-slate-900/70 dark:border-slate-600 space-y-1">
                      <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
                        Generated by{' '}
                        {msg.generatedImageProvider === 'cloudflare'
                          ? 'Cloudflare Flux'
                          : msg.generatedImageProvider === 'gemini'
                            ? 'Gemini'
                            : msg.generatedImageProvider === 'modelslab'
                              ? 'ModelsLab'
                              : 'AI'}
                      </p>
                      {msg.generatedImageModel ? (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate" title={msg.generatedImageModel}>
                          Model: {msg.generatedImageModel}
                        </p>
                      ) : null}
                      {msg.generatedImageFallbackReason ? (
                        <p className="text-[11px] text-amber-700 dark:text-amber-300">
                          {msg.generatedImageFallbackReason}
                        </p>
                      ) : null}
                    </div>
                  </div>
                )}
                {!isUser && msg.generatedAudioUrl && (
                  <div className="rounded-xl border border-slate-200 dark:border-slate-600 p-3 bg-white dark:bg-slate-900 max-w-sm">
                    <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-2 flex items-center gap-1">
                      <Mic className="w-3.5 h-3.5" />
                      Voice-over
                    </p>
                    <audio controls src={msg.generatedAudioUrl} className="w-full" />
                  </div>
                )}

                {/* Chat bubble */}
                {isUser && (msg.images?.length || msg.image_preview_url) && (
                  <div className="flex flex-wrap gap-2 max-w-md">
                    {(msg.images?.length
                      ? msg.images.map((img, imgIndex) => ({
                          key: `${index}-img-${imgIndex}`,
                          src: img.image_preview_url,
                        }))
                      : [{ key: `${index}-img-0`, src: msg.image_preview_url }]
                    )
                      .filter((item) => Boolean(item.src))
                      .map((item) => (
                        <div
                          key={item.key}
                          className="rounded-xl overflow-hidden border border-brand-200 dark:border-slate-500 w-28"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={item.src!}
                            alt="Reference attachment"
                            className="w-full h-auto max-h-28 object-cover bg-white dark:bg-slate-900"
                          />
                        </div>
                      ))}
                  </div>
                )}
                {showTextBubble && (
                <div
                  className={`group relative rounded-2xl px-4 py-2.5 text-sm ${
                    isUser
                      ? 'bg-brand-600 text-white rounded-br-sm'
                      : 'bg-slate-100 text-slate-800 rounded-bl-sm dark:bg-slate-700 dark:text-slate-100'
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{msg.content}</p>

                  <button
                    onClick={() => copyMessage(msg.content, index)}
                    className={`absolute -bottom-2 ${
                      isUser ? '-left-2' : '-right-2'
                    } opacity-0 group-hover:opacity-100 transition-opacity bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:bg-slate-50 dark:bg-slate-700 dark:border-slate-500 dark:hover:bg-slate-600`}
                    title="Copy text"
                  >
                    {copiedIndex === index ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5 text-slate-500" />
                    )}
                  </button>
                </div>
                )}

                {!isUser && msgIntent === 'create_image' && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => generateImage(index)}
                      disabled={generatingImageIndex === index || !imageReady}
                      className="inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 border border-brand-200 text-brand-700 hover:bg-brand-50 disabled:opacity-50 dark:border-slate-500 dark:text-gold-300 dark:hover:bg-slate-700"
                    >
                      {generatingImageIndex === index ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <ImageIcon className="w-3.5 h-3.5" />
                      )}
                      {msg.generatedImageUrl ? 'Regenerate image' : 'Generate image'}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSavePrompt(msg.content)}
                      className="inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700"
                      title="Save this prompt text for reuse (not the image file)"
                    >
                      <Bookmark className="w-3.5 h-3.5" />
                      Save prompt
                    </button>
                  </div>
                )}
                {!isUser && msgIntent === 'create_voice' && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => generateVoice(index)}
                      disabled={generatingVoiceIndex === index}
                      className="inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 border border-brand-200 text-brand-700 hover:bg-brand-50 disabled:opacity-50 dark:border-slate-500 dark:text-gold-300 dark:hover:bg-slate-700"
                    >
                      {generatingVoiceIndex === index ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Mic className="w-3.5 h-3.5" />
                      )}
                      Generate voice
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSavePrompt(msg.content)}
                      className="inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700"
                      title="Save this script text for reuse (not the audio file)"
                    >
                      <Bookmark className="w-3.5 h-3.5" />
                      Save prompt
                    </button>
                  </div>
                )}
                {!isUser && msgIntent === 'prompt' && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleSavePrompt(msg.content)}
                      className="inline-flex items-center gap-1 text-xs font-medium rounded-lg px-2.5 py-1.5 border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700"
                      title="Save this prompt text for reuse in Create image or Create voice"
                    >
                      <Bookmark className="w-3.5 h-3.5" />
                      Save prompt
                    </button>
                  </div>
                )}
              </div>

              {isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center dark:bg-slate-600">
                  <User className="w-4 h-4 text-slate-600 dark:text-slate-200" />
                </div>
              )}
            </div>
          );
        })}

        {sending && (
          <div className="flex gap-3 justify-start">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center dark:bg-brand-900/60">
              <Bot className="w-4 h-4 text-brand-700 dark:text-gold-300" />
            </div>
            <div className="bg-slate-100 text-slate-500 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm inline-flex items-center gap-2 dark:bg-slate-700 dark:text-slate-300">
              <Loader2 className="w-4 h-4 animate-spin" />
              {creationIntent === 'create_image' ? 'Preparing your image…' : 'Thinking…'}
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-slate-200 dark:border-slate-600 p-4 space-y-3">
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
            What do you want to create?
          </p>
          <div className="flex flex-wrap gap-2">
            {CREATION_MODES.map((mode) => {
              const Icon = mode.icon;
              const selected = creationIntent === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setCreationIntent(mode.id)}
                  title={mode.description}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    selected
                      ? 'border-brand-600 bg-brand-50 text-brand-800 ring-2 ring-brand-500/20 dark:border-gold-400 dark:bg-brand-900/50 dark:text-gold-200'
                      : 'border-slate-200 text-slate-600 hover:border-brand-300 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {mode.label}
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{activeMode.description}</p>
        </div>

        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            multiple
            className="hidden"
            onChange={handleImageFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={sending || isListening || pendingAttachments.length >= MAX_REFERENCE_IMAGES}
            className="inline-flex shrink-0 items-center justify-center rounded-lg border border-slate-300 p-2.5 text-slate-600 hover:bg-slate-50 hover:text-brand-700 disabled:opacity-50 dark:border-slate-500 dark:text-slate-300 dark:hover:bg-slate-700"
            title={`Attach up to ${MAX_REFERENCE_IMAGES} reference images (${pendingAttachments.length}/${MAX_REFERENCE_IMAGES})`}
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              if (!speechSupported) {
                toast.error(
                  'Voice typing needs Chrome or Edge. Type your prompt or use another browser.'
                );
                return;
              }
              toggleListening();
            }}
            disabled={sending}
            className={`inline-flex shrink-0 items-center justify-center rounded-lg border p-2.5 transition-colors disabled:opacity-50 ${
              isListening
                ? 'border-red-400 bg-red-50 text-red-600 animate-pulse dark:border-red-500 dark:bg-red-950/40 dark:text-red-400'
                : 'border-slate-300 text-slate-600 hover:bg-slate-50 hover:text-brand-700 dark:border-slate-500 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
            title={
              isListening
                ? 'Stop voice typing'
                : 'Speak your prompt — text appears in the box (Chrome / Edge)'
            }
          >
            <Mic className="w-4 h-4" />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? 'Listening… speak your prompt, then click the mic to stop.'
                : pendingAttachments.length
                  ? 'Add optional details about what to create from these references…'
                  : activeMode.placeholder
            }
            rows={2}
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-700 dark:border-slate-500 dark:text-slate-100 dark:placeholder-slate-400"
            disabled={sending}
          />
          <button
            onClick={sendMessage}
            disabled={sending || (!input.trim() && !pendingAttachments.length)}
            className="inline-flex items-center gap-1.5 text-sm font-medium rounded-lg px-4 py-2.5 bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
            {creationIntent === 'create_image' && !pendingAttachments.length ? 'Create' : 'Send'}
          </button>
        </div>
        {pendingAttachments.length > 0 && (
          <div className="rounded-lg border border-brand-200 bg-brand-50/80 px-3 py-2 dark:border-slate-500 dark:bg-slate-700/60 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
                Reference images ({pendingAttachments.length}/{MAX_REFERENCE_IMAGES}) — the AI
                analyzes all of them together for your{' '}
                {creationIntent === 'create_image' ? 'generated visual' : 'prompt'}.
              </p>
              <button
                type="button"
                onClick={clearPendingAttachments}
                className="text-xs text-slate-500 hover:text-red-600 dark:text-slate-400"
              >
                Clear all
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {pendingAttachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="relative group rounded-md overflow-hidden border border-slate-200 dark:border-slate-500"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={attachment.previewUrl}
                    alt={attachment.name}
                    className="h-14 w-14 object-cover bg-white dark:bg-slate-900"
                    title={attachment.name}
                  />
                  <button
                    type="button"
                    onClick={() => removePendingAttachment(attachment.id)}
                    className="absolute top-0.5 right-0.5 rounded-full bg-black/60 p-0.5 text-white opacity-90 hover:bg-red-600"
                    title={`Remove ${attachment.name}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {isListening && (
          <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            Voice typing active — speak clearly, then click the mic again to stop. Click Send when
            ready.
          </p>
        )}
        <p className="text-xs text-slate-400">
          {creationIntent === 'create_image' &&
            'Create image — describe your shot; the image appears below (no prompt text).'}
          {creationIntent === 'create_voice' &&
            'Create voice — AI writes the script; click Generate voice when you are ready.'}
          {creationIntent === 'prompt' &&
            'Write prompt — copy the reply for Meta AI or Google Flow. No in-app generation.'}
        </p>
      </div>
    </div>
  );
}
