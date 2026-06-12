'use client';

import ChatInterface from '@/components/creation/ChatInterface';

export default function CreationPage() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-slate-900 mb-2">🎨 Content Creation</h1>
        <p className="text-gray-600">
          Chat with free AI models to brainstorm ideas and craft prompts. When you need an image or
          video, jump straight into Google Gemini.
        </p>
      </div>

      {/* How it works */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-brand-600">
          <div className="text-2xl mb-1">💬</div>
          <h3 className="font-semibold text-sm text-slate-900">1. Chat with AI</h3>
          <p className="text-xs text-gray-500 mt-1">
            Pick a free model and brainstorm ideas, captions, or prompts
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gold-500">
          <div className="text-2xl mb-1">📋</div>
          <h3 className="font-semibold text-sm text-slate-900">2. Copy a Prompt</h3>
          <p className="text-xs text-gray-500 mt-1">
            Copy any AI reply to reuse it as a prompt elsewhere
          </p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-emerald-500">
          <div className="text-2xl mb-1">✨</div>
          <h3 className="font-semibold text-sm text-slate-900">3. Image / Video in Gemini</h3>
          <p className="text-xs text-gray-500 mt-1">
            Click Create in Gemini to make photos or videos there
          </p>
        </div>
      </div>

      {/* Chatbot */}
      <ChatInterface />

      {/* Info Box */}
      <div className="mt-8 bg-brand-50 border border-brand-100 rounded-lg p-6">
        <h3 className="font-semibold text-brand-900 mb-2">💡 How This Works</h3>
        <ul className="text-sm text-slate-700 space-y-1.5">
          <li>• <strong>Chat</strong> uses its own Gemini key (<code>CREATION_GEMINI_API_KEY</code>) — separate from Content Posting</li>
          <li>• <strong>Copy any message</strong> to reuse it as a prompt elsewhere</li>
          <li>• <strong>Create Image / Video in Gemini</strong> — both buttons open Google Gemini in a new tab</li>
          <li>• This chatbot only chats — image and video creation happen in Gemini</li>
          <li>• Get a <strong>2nd free key</strong> at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-brand-700 underline">aistudio.google.com/apikey</a> and paste it in <code>CREATION_GEMINI_API_KEY</code></li>
        </ul>
      </div>
    </div>
  );
}
