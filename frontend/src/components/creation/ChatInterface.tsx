'use client';

import React, { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Send,
  Video,
  Copy,
  Check,
  Loader2,
  Bot,
  User,
  Trash2,
  Package,
  Tag,
  Box,
  Mic,
  Users,
  Clapperboard,
  Sparkles,
  ImageIcon,
  Paperclip,
  X,
} from 'lucide-react';
import { API_ENDPOINTS, API_CONFIG, apiFetch, fetchWithTimeout } from '@/lib/api-client';
import { useSpeechToText } from '@/hooks/useSpeechToText';
import type {
  ChatMessage,
  ChatResponse,
  CreationIntent,
  CreationModelsResponse,
  ImageGenerateResponse,
  MatchedProduct,
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

const META_AI_FALLBACK_URL = 'https://www.meta.ai/';
const GOOGLE_FLOW_CHARACTERS_FALLBACK_URL =
  'https://labs.google/fx/tools/flow/project/cc16a3ce-33ec-4248-bb1a-3341c7817479/characters';
const GOOGLE_FLOW_FINAL_PRODUCT_FALLBACK_URL =
  'https://labs.google/fx/tools/flow/project/0b5aa7ed-bd40-490d-af9a-24208f855710';

const MAX_REFERENCE_IMAGE_BYTES = 4 * 1024 * 1024;
const ALLOWED_REFERENCE_IMAGE_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
]);

interface PendingAttachment {
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
  return messages.map((m) => {
    const entry: ChatMessage = { role: m.role, content: m.content };
    if (m.image_base64) {
      entry.image_base64 = m.image_base64;
      entry.image_mime_type = m.image_mime_type ?? 'image/jpeg';
    }
    return entry;
  });
}
const CATEGORY_COLOURS: Record<string, string> = {
  'Pickles': 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  'Chutneys': 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  'Pastes': 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
  'Sauces': 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  'Himalayan Salt': 'bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300',
  'Salt': 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  'Specialty Salts': 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
  'Vermicelli & Sweets': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  'Fried Onion': 'bg-lime-100 text-lime-800 dark:bg-lime-900/40 dark:text-lime-300',
  'Moringa Products': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  'Moringa Beauty & Personal Care': 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300',
  'Masalas & Spice Blends': 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300',
};

function categoryColour(category: string): string {
  return CATEGORY_COLOURS[category] ?? 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200';
}

// ---------------------------------------------------------------------------
// Product Card component
// ---------------------------------------------------------------------------

function ProductCard({ product }: { product: MatchedProduct }) {
  return (
    <div className="mb-3 rounded-xl border border-brand-200 bg-gradient-to-br from-brand-50 to-white shadow-sm overflow-hidden dark:from-brand-950/40 dark:to-slate-800 dark:border-brand-700">
      {/* Header strip */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-brand-600 dark:bg-brand-800">
        <Package className="w-4 h-4 text-white flex-shrink-0" />
        <span className="text-sm font-semibold text-white truncate">{product.name}</span>
        <span className="ml-auto text-xs text-brand-200 flex-shrink-0">{product.brand}</span>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-2.5">
        {/* Category badge */}
        <div className="flex items-center gap-1.5">
          <Tag className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${categoryColour(product.category)}`}>
            {product.category}
          </span>
        </div>

        {/* Description */}
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {product.description}
        </p>

        {/* Packaging */}
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Box className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
              Available Packaging
            </span>
          </div>
          <ul className="space-y-1">
            {product.packaging.map((pkg, i) => (
              <li
                key={i}
                className="text-xs text-slate-600 dark:text-slate-300 flex items-start gap-1.5"
              >
                <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-brand-400 flex-shrink-0" />
                {pkg}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Extended message type (includes optional matched product)
// ---------------------------------------------------------------------------

interface ExtendedChatMessage extends ChatMessage {
  matchedProduct?: MatchedProduct | null;
  generatedImageUrl?: string | null;
  generatedAudioUrl?: string | null;
  intent?: CreationIntent;
}

// ---------------------------------------------------------------------------
// Main ChatInterface
// ---------------------------------------------------------------------------

export default function ChatInterface() {
  const [modelLabel, setModelLabel] = useState<string>('Loading…');
  const [metaAiUrl, setMetaAiUrl] = useState<string>(META_AI_FALLBACK_URL);
  const [googleFlowCharactersUrl, setGoogleFlowCharactersUrl] = useState<string>(
    GOOGLE_FLOW_CHARACTERS_FALLBACK_URL
  );
  const [googleFlowFinalProductUrl, setGoogleFlowFinalProductUrl] = useState<string>(
    GOOGLE_FLOW_FINAL_PRODUCT_FALLBACK_URL
  );
  const [chatReady, setChatReady] = useState<boolean>(true);
  const [imageReady, setImageReady] = useState<boolean>(false);
  const [voiceMoods, setVoiceMoods] = useState<{ id: string; label: string }[]>([]);
  const [voiceMood, setVoiceMood] = useState<string>('professional');
  const [creationIntent, setCreationIntent] = useState<CreationIntent>('create_image');

  const activeMode =
    CREATION_MODES.find((m) => m.id === creationIntent) ?? CREATION_MODES[0];

  const [messages, setMessages] = useState<ExtendedChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [generatingImageIndex, setGeneratingImageIndex] = useState<number | null>(null);
  const [generatingVoiceIndex, setGeneratingVoiceIndex] = useState<number | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    lang: 'en-US',
    onFinalTranscript: appendFinalTranscript,
    onError: (message) => toast.error(message),
  });

  useEffect(() => {
    if (sending && isListening) {
      stopSpeechListening();
    }
  }, [sending, isListening, stopSpeechListening]);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const res = await fetchWithTimeout(API_ENDPOINTS.CREATION_MODELS);
        if (!res.ok) throw new Error('Failed to load models');
        const data: CreationModelsResponse = await res.json();
        setModelLabel(data.models[0]?.label ?? 'AI Assistant');
        setMetaAiUrl(data.meta_ai_web_url || META_AI_FALLBACK_URL);
        setGoogleFlowCharactersUrl(
          data.google_flow_characters_url || GOOGLE_FLOW_CHARACTERS_FALLBACK_URL
        );
        setGoogleFlowFinalProductUrl(
          data.google_flow_final_product_url || GOOGLE_FLOW_FINAL_PRODUCT_FALLBACK_URL
        );
        setChatReady(data.chat_ready);
        setImageReady(Boolean(data.image_ready));
        setVoiceMoods(data.voice_moods ?? []);
      } catch {
        toast.error('Could not load AI models. Is the backend running?');
      }
    };
    loadModels();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const sendMessage = async () => {
    const text = input.trim();
    const hasAttachment = Boolean(pendingAttachment);
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
        'Analyze the attached reference image and write a detailed Essence product marketing prompt that matches its style.',
      ...(pendingAttachment
        ? {
            image_base64: pendingAttachment.base64,
            image_mime_type: pendingAttachment.mimeType,
            image_preview_url: pendingAttachment.previewUrl,
          }
        : {}),
    };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setPendingAttachment(null);
    setSending(true);

    try {
      const res = await apiFetch(API_ENDPOINTS.CREATION_CHAT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: '',
          intent: creationIntent,
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
        matchedProduct: data.matched_product ?? null,
        intent: creationIntent,
      };
      const assistantIndex = nextMessages.length;
      setMessages((prev) => [...prev, assistantMsg]);

      if (creationIntent === 'create_image' && imageReady) {
        void runGenerateImage(assistantIndex, data.reply);
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

  const openMetaAi = () => {
    window.open(metaAiUrl, '_blank', 'noopener,noreferrer');
  };

  const openGoogleFlowCharacters = () => {
    window.open(googleFlowCharactersUrl, '_blank', 'noopener,noreferrer');
  };

  const openGoogleFlowFinalProduct = () => {
    window.open(googleFlowFinalProductUrl, '_blank', 'noopener,noreferrer');
  };

  const runGenerateImage = async (index: number, promptText: string) => {
    if (!imageReady) {
      toast.error(
        'Image API not configured. Set IMAGE_PROVIDER=cloudflare (or modelslab/gemini) and the matching keys in backend .env, then restart.'
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
      setMessages((prev) =>
        prev.map((m, i) =>
          i === index ? { ...m, generatedImageUrl: data.media_url } : m
        )
      );
      toast.success('Image generated in-app');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Image generation failed');
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
        body: JSON.stringify({ text: scriptText, mood: voiceMood }),
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

  const clearPendingAttachment = () => {
    setPendingAttachment(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleImageFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ALLOWED_REFERENCE_IMAGE_TYPES.has(file.type)) {
      toast.error('Use JPEG, PNG, WebP, or GIF.');
      e.target.value = '';
      return;
    }
    if (file.size > MAX_REFERENCE_IMAGE_BYTES) {
      toast.error('Image must be under 4 MB.');
      e.target.value = '';
      return;
    }

    try {
      const { base64, previewUrl, mimeType } = await readImageFile(file);
      setPendingAttachment({
        base64,
        previewUrl,
        mimeType,
        name: file.name,
      });
    } catch {
      toast.error('Could not read image file.');
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[70vh] dark:bg-slate-800 dark:border-slate-600">
      {/* Toolbar */}
      <div className="flex flex-nowrap items-center gap-2 p-4 border-b border-slate-200 overflow-x-auto dark:border-slate-600">
        <span className="text-sm text-slate-600 bg-slate-100 rounded-lg px-3 py-1.5 shrink-0 dark:bg-slate-700 dark:text-slate-200">
          {modelLabel}
        </span>

        <div className="flex-1 min-w-2" />

        <button
          onClick={openMetaAi}
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors dark:text-gold-300 dark:hover:text-gold-200 dark:border-slate-500 dark:hover:bg-slate-700"
          title="Open Meta AI to generate a video"
        >
          <Video className="w-4 h-4" />
          Video in Meta AI
        </button>
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
          onClick={openGoogleFlowCharacters}
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors dark:text-gold-300 dark:hover:text-gold-200 dark:border-slate-500 dark:hover:bg-slate-700"
          title="Create characters in Google Flow"
        >
          <Users className="w-4 h-4" />
          Create Characters in Google Flow
        </button>
        <button
          onClick={openGoogleFlowFinalProduct}
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors dark:text-gold-300 dark:hover:text-gold-200 dark:border-slate-500 dark:hover:bg-slate-700"
          title="Create final product video in Google Flow"
        >
          <Clapperboard className="w-4 h-4" />
          Create Final Product on Flow AI
        </button>

        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="inline-flex shrink-0 items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors"
            title="Clear conversation"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
            <Bot className="w-12 h-12 mb-3 text-slate-300" />
            <p className="text-sm max-w-md mb-4">
              Select a mode below — <strong>Create image</strong> generates visuals in-app,{' '}
              <strong>Create voice</strong> writes a script you can turn into audio, and{' '}
              <strong>Write prompt</strong> gives copy-paste text for Meta AI or Flow.
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
                {/* Product card — shown only on assistant messages with a matched product */}
                {!isUser && msg.matchedProduct && (
                  <ProductCard product={msg.matchedProduct} />
                )}

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
                {!isUser && msg.generatedImageUrl && (
                  <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-600 max-w-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={msg.generatedImageUrl}
                      alt="Generated product visual"
                      className="w-full h-auto object-contain bg-white dark:bg-slate-900"
                    />
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
                {isUser && msg.image_preview_url && (
                  <div className="rounded-xl overflow-hidden border border-brand-200 dark:border-slate-500 max-w-xs">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={msg.image_preview_url}
                      alt="Reference attachment"
                      className="w-full h-auto max-h-48 object-contain bg-white dark:bg-slate-900"
                    />
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
                      Regenerate image
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
            className="hidden"
            onChange={handleImageFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={sending || isListening}
            className="inline-flex shrink-0 items-center justify-center rounded-lg border border-slate-300 p-2.5 text-slate-600 hover:bg-slate-50 hover:text-brand-700 disabled:opacity-50 dark:border-slate-500 dark:text-slate-300 dark:hover:bg-slate-700"
            title="Attach reference image for vision-based prompt writing"
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
                : pendingAttachment
                  ? 'Describe the Essence product to adapt to this reference (optional)…'
                  : activeMode.placeholder
            }
            rows={2}
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-700 dark:border-slate-500 dark:text-slate-100 dark:placeholder-slate-400"
            disabled={sending}
          />
          <button
            onClick={sendMessage}
            disabled={sending || (!input.trim() && !pendingAttachment)}
            className="inline-flex items-center gap-1.5 text-sm font-medium rounded-lg px-4 py-2.5 bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
            {creationIntent === 'create_image' && !pendingAttachment ? 'Create' : 'Send'}
          </button>
        </div>
        {pendingAttachment && (
          <div className="flex items-center gap-3 rounded-lg border border-brand-200 bg-brand-50/80 px-3 py-2 dark:border-slate-500 dark:bg-slate-700/60">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={pendingAttachment.previewUrl}
              alt="Pending reference"
              className="h-14 w-14 rounded-md object-cover border border-slate-200 dark:border-slate-500"
            />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">
                {pendingAttachment.name}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Reference image — AI uses it to craft your{' '}
                {creationIntent === 'create_image' ? 'generated visual' : 'prompt'}.
              </p>
            </div>
            <button
              type="button"
              onClick={clearPendingAttachment}
              className="shrink-0 rounded-full p-1 text-slate-500 hover:bg-white hover:text-red-600 dark:hover:bg-slate-600"
              title="Remove attachment"
            >
              <X className="w-4 h-4" />
            </button>
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
