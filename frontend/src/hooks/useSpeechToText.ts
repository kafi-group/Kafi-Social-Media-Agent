'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionInstance) | null {
  if (typeof window === 'undefined') return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface UseSpeechToTextOptions {
  /** BCP-47 language tag, e.g. en-US */
  lang?: string;
  /** Called with finalized transcript chunks to append to the composer. */
  onFinalTranscript: (text: string) => void;
  onError?: (message: string) => void;
}

/**
 * Browser speech-to-text via Web Speech API (Chrome, Edge, Safari).
 * No backend or API key required — mic permission only.
 */
export function useSpeechToText({
  lang = 'en-US',
  onFinalTranscript,
  onError,
}: UseSpeechToTextOptions) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const onFinalRef = useRef(onFinalTranscript);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onFinalRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    setIsSupported(Boolean(getSpeechRecognitionCtor()));
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      onErrorRef.current?.(
        'Speech recognition is not supported in this browser. Try Chrome or Edge.'
      );
      return;
    }

    stopListening();

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const chunk = result[0]?.transcript ?? '';
        if (result.isFinal) {
          const trimmed = chunk.trim();
          if (trimmed) onFinalRef.current(trimmed);
        } else {
          interim += chunk;
        }
      }
      // Interim chunks are ignored — only finals are appended for stable typing.
      void interim;
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'aborted' || event.error === 'no-speech') {
        return;
      }
      const messages: Record<string, string> = {
        'not-allowed': 'Microphone permission denied. Allow mic access in browser settings.',
        'service-not-allowed': 'Speech recognition is blocked on this page.',
        network: 'Speech recognition needs an internet connection.',
      };
      onErrorRef.current?.(
        messages[event.error] ?? `Speech recognition error: ${event.error}`
      );
      stopListening();
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    try {
      recognitionRef.current = recognition;
      recognition.start();
      setIsListening(true);
    } catch {
      onErrorRef.current?.('Could not start microphone. Try again.');
      stopListening();
    }
  }, [lang, stopListening]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  return { isListening, isSupported, toggleListening, stopListening };
}
