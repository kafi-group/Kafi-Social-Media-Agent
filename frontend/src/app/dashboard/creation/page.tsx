'use client';

import ChatInterface from '@/components/creation/ChatInterface';

export default function CreationPage() {
  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-slate-900 mb-2 dark:text-slate-100">🎨 Prompt Studio</h1>
        <p className="text-gray-600 dark:text-slate-400">
          Chat for Essence product prompts, then generate <strong>images</strong> (Gemini API) and{' '}
          <strong>voice-overs</strong> (free TTS) in-app. Use Meta AI and Google Flow for video.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-brand-600 dark:bg-slate-800">
          <div className="text-2xl mb-1">💬</div>
          <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">1. Describe the shot</h3>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
            Name the product, packaging, and use case (Instagram feed, Amazon listing, reel)
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gold-500 dark:bg-slate-800">
          <div className="text-2xl mb-1">🖼️</div>
          <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">2. Generate image & voice</h3>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
            Click Generate image or Generate voice on the assistant reply — pick a voice mood in the toolbar
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-emerald-500 dark:bg-slate-800">
          <div className="text-2xl mb-1">🎬</div>
          <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">3. Video in Meta AI / Flow</h3>
          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
            Use the video links for motion clips — combine with your generated image and voice-over
          </p>
        </div>
      </div>

      <ChatInterface />

      <div className="mt-8 bg-brand-50 border border-brand-100 rounded-lg p-6 dark:bg-brand-950/40 dark:border-brand-800/60">
        <h3 className="font-semibold text-brand-900 dark:text-brand-200 mb-2">💡 Tips</h3>
        <ul className="text-sm text-slate-700 dark:text-slate-300 space-y-1.5">
          <li>• Chat uses <code>CREATION_GEMINI_API_KEY</code> — separate from Content Posting</li>
          <li>• Images use <code>IMAGE_GEMINI_API_KEY</code> on a <strong>different Google account</strong> so quotas stay isolated</li>
          <li>• Voice-over is free (edge-tts) — choose mood in the toolbar before clicking Generate voice</li>
          <li>• Video: open <strong>Meta AI</strong> or <strong>Google Flow</strong> from the top buttons</li>
          <li>• Mention packaging format (330g glass jar vs 1kg PET) for accurate prompts</li>
        </ul>
      </div>
    </div>
  );
}
