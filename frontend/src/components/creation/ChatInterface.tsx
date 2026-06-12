'use client';

import React, { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Send,
  Image as ImageIcon,
  Video,
  Copy,
  Check,
  Loader2,
  Bot,
  User,
  Trash2,
} from 'lucide-react';
import { API_ENDPOINTS } from '@/lib/api-client';
import type {
  ChatMessage,
  ChatResponse,
  CreationModelsResponse,
} from '@/lib/types';

const GEMINI_FALLBACK_URL = 'https://gemini.google.com/app';

export default function ChatInterface() {
  const [modelLabel, setModelLabel] = useState<string>('Loading…');
  const [geminiUrl, setGeminiUrl] = useState<string>(GEMINI_FALLBACK_URL);
  const [chatReady, setChatReady] = useState<boolean>(true);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const res = await fetch(API_ENDPOINTS.CREATION_MODELS);
        if (!res.ok) throw new Error('Failed to load models');
        const data: CreationModelsResponse = await res.json();
        setModelLabel(data.models[0]?.label ?? 'AI Assistant');
        setGeminiUrl(data.gemini_web_url || GEMINI_FALLBACK_URL);
        setChatReady(data.chat_ready);
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
    if (!text || sending) return;

    if (!chatReady) {
      toast.error(
        'Chat is not configured. Add CREATION_GEMINI_API_KEY in the backend .env (2nd free key from aistudio.google.com/apikey).'
      );
      return;
    }

    const userMsg: ChatMessage = { role: 'user', content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setSending(true);

    try {
      const res = await fetch(API_ENDPOINTS.CREATION_CHAT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: '',
          messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Chat request failed');
      }
      const data: ChatResponse = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
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

  const openGemini = () => {
    window.open(geminiUrl, '_blank', 'noopener,noreferrer');
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

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[70vh]">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 p-4 border-b border-slate-200">
        <span className="text-sm text-slate-600 bg-slate-100 rounded-lg px-3 py-1.5">
          {modelLabel}
        </span>

        <div className="flex-1" />

        {/* Image + video both open Gemini */}
        <button
          onClick={openGemini}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors"
          title="Create an image in Google Gemini"
        >
          <ImageIcon className="w-4 h-4" />
          Create Image in Gemini
        </button>
        <button
          onClick={openGemini}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-900 border border-brand-200 hover:bg-brand-50 rounded-lg px-3 py-1.5 transition-colors"
          title="Create a video in Google Gemini"
        >
          <Video className="w-4 h-4" />
          Create Video in Gemini
        </button>

        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors"
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
            <p className="text-sm max-w-md">
              Chat with Google Gemini — brainstorm ideas, write captions, or craft prompts. When
              you need an <strong>image or video</strong>, copy your prompt and use the
              <strong> Create in Gemini</strong> buttons above.
            </p>
          </div>
        )}

        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <div key={index} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
              {!isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-brand-700" />
                </div>
              )}

              <div
                className={`group relative max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${
                  isUser
                    ? 'bg-brand-600 text-white rounded-br-sm'
                    : 'bg-slate-100 text-slate-800 rounded-bl-sm'
                }`}
              >
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>

                <button
                  onClick={() => copyMessage(msg.content, index)}
                  className={`absolute -bottom-2 ${
                    isUser ? '-left-2' : '-right-2'
                  } opacity-0 group-hover:opacity-100 transition-opacity bg-white border border-slate-200 rounded-full p-1.5 shadow-sm hover:bg-slate-50`}
                  title="Copy text"
                >
                  {copiedIndex === index ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5 text-slate-500" />
                  )}
                </button>
              </div>

              {isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                  <User className="w-4 h-4 text-slate-600" />
                </div>
              )}
            </div>
          );
        })}

        {sending && (
          <div className="flex gap-3 justify-start">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center">
              <Bot className="w-4 h-4 text-brand-700" />
            </div>
            <div className="bg-slate-100 text-slate-500 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm inline-flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Thinking…
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-slate-200 p-4">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message the AI…"
            rows={2}
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            disabled={sending}
          />
          <button
            onClick={sendMessage}
            disabled={sending || !input.trim()}
            className="inline-flex items-center gap-1.5 text-sm font-medium rounded-lg px-4 py-2.5 bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Press Enter to send, Shift+Enter for a new line. For images or videos, use the
          &ldquo;Create in Gemini&rdquo; buttons above.
        </p>
      </div>
    </div>
  );
}
