'use client';

import { useState, useEffect } from 'react';
import { ContentGenerationResponse, ContentRegenerateRequest } from '@/lib/types';

export interface GenerationContext {
  topic: string;
  brand_context: string;
  tone: string;
  target_audience: string;
  call_to_action: string;
  additional_instructions: string;
}

interface GeneratedContentDisplayProps {
  contents: ContentGenerationResponse[];
  mediaPreview?: string | null;
  mediaType?: 'image' | 'video' | null;
  mediaFileName?: string;
  generationContext?: GenerationContext;
  onContentUpdate?: (contentId: number, updatedTitle: string, updatedBody: string) => void;
  onRegenerate?: (
    contentId: number,
    payload: ContentRegenerateRequest
  ) => Promise<ContentGenerationResponse>;
}

const PLATFORM_COLORS: Record<string, string> = {
  linkedin: 'from-blue-600 to-blue-700',
  twitter: 'from-black to-gray-800',
  facebook: 'from-blue-500 to-blue-600',
  instagram: 'from-pink-500 to-purple-500',
  tiktok: 'from-black to-gray-900',
  youtube: 'from-red-600 to-red-700',
  email: 'from-gray-600 to-gray-700',
  whatsapp: 'from-green-500 to-green-600',
};

const PLATFORM_ICONS: Record<string, string> = {
  linkedin: '💼',
  twitter: '𝕏',
  facebook: '👍',
  instagram: '📷',
  tiktok: '🎵',
  youtube: '▶️',
  email: '✉️',
  whatsapp: '💬',
};

export default function GeneratedContentDisplay({
  contents,
  mediaPreview,
  mediaType,
  mediaFileName,
  generationContext,
  onContentUpdate,
  onRegenerate,
}: GeneratedContentDisplayProps) {
  const [selectedContent, setSelectedContent] = useState<ContentGenerationResponse | null>(
    contents.length > 0 ? contents[0] : null
  );
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [editingContentId, setEditingContentId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editBody, setEditBody] = useState('');
  const [showRegeneratePanel, setShowRegeneratePanel] = useState(false);
  const [regenerationInstructions, setRegenerationInstructions] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedContent) return;
    const updated = contents.find((c) => c.content_id === selectedContent.content_id);
    if (updated) setSelectedContent(updated);
  }, [contents, selectedContent?.content_id]);

  const copyToClipboard = (text: string, contentId: number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(contentId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const startEditing = (content: ContentGenerationResponse) => {
    setEditingContentId(content.content_id);
    setEditTitle(content.title);
    setEditBody(content.body);
    setShowRegeneratePanel(false);
  };

  const cancelEditing = () => {
    setEditingContentId(null);
    setEditTitle('');
    setEditBody('');
  };

  const saveEditing = () => {
    if (editingContentId === null) return;
    if (!editTitle.trim()) return;
    onContentUpdate?.(editingContentId, editTitle.trim(), editBody.trim());
    setSelectedContent((prev) =>
      prev?.content_id === editingContentId
        ? { ...prev, title: editTitle.trim(), body: editBody.trim() }
        : prev
    );
    setEditingContentId(null);
  };

  const handleRegenerate = async () => {
    if (!selectedContent || !onRegenerate || !generationContext) return;

    setRegenerating(true);
    setRegenerateError(null);

    try {
      const updated = await onRegenerate(selectedContent.content_id, {
        topic: generationContext.topic,
        brand_context: generationContext.brand_context,
        tone: generationContext.tone,
        target_audience: generationContext.target_audience,
        call_to_action: generationContext.call_to_action,
        additional_instructions: generationContext.additional_instructions,
        regeneration_instructions: regenerationInstructions.trim(),
      });

      setSelectedContent(updated);
      setRegenerationInstructions('');
      setShowRegeneratePanel(false);
      cancelEditing();
    } catch (err) {
      setRegenerateError(err instanceof Error ? err.message : 'Failed to regenerate caption');
    } finally {
      setRegenerating(false);
    }
  };

  if (contents.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-8 text-center">
        <p className="text-gray-600">No content generated yet.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Media Preview Banner */}
      {mediaPreview && (
        <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-xl p-4 mb-6 border border-purple-200">
          <div className="flex items-center gap-4">
            <div className="flex-shrink-0 w-20 h-20 rounded-lg overflow-hidden bg-white shadow-sm">
              {mediaType === 'video' ? (
                <video src={mediaPreview} className="w-full h-full object-cover" />
              ) : (
                <img src={mediaPreview} alt="Media preview" className="w-full h-full object-cover" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-700">📎 Attached Media</p>
              <p className="text-sm text-gray-500 truncate">{mediaFileName || 'Media file'}</p>
              <p className="text-xs text-gray-400">
                This media will be posted alongside the caption
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Content List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-md p-4">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              ✨ Generated Captions
            </h2>
            <div className="space-y-2">
              {contents.map((content) => (
                <button
                  key={content.content_id}
                  onClick={() => {
                    setSelectedContent(content);
                    cancelEditing();
                    setShowRegeneratePanel(false);
                    setRegenerationInstructions('');
                    setRegenerateError(null);
                  }}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    selectedContent?.content_id === content.content_id
                      ? 'bg-blue-50 border-l-4 border-blue-500'
                      : 'bg-gray-50 hover:bg-gray-100 border-l-4 border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{PLATFORM_ICONS[content.platform]}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 capitalize">
                        {content.platform}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{content.title}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content Detail */}
        <div className="lg:col-span-2">
          {selectedContent && (
            <div className="bg-white rounded-lg shadow-md overflow-hidden">
              {/* Platform Header */}
              <div
                className={`bg-gradient-to-r ${
                  PLATFORM_COLORS[selectedContent.platform] || 'from-gray-600 to-gray-700'
                } text-white p-6`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-4xl">{PLATFORM_ICONS[selectedContent.platform]}</span>
                  <div>
                    <h3 className="text-2xl font-bold capitalize">{selectedContent.platform}</h3>
                    <p className="text-white/80 text-sm">
                      {new Date(selectedContent.generated_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              <div className="p-6">
                {/* Media Preview in Detail */}
                {mediaPreview && (
                  <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
                    {mediaType === 'video' ? (
                      <video src={mediaPreview} className="w-full max-h-80 object-contain bg-black/5" controls />
                    ) : (
                      <img src={mediaPreview} alt="Attached media" className="w-full max-h-80 object-contain bg-black/5" />
                    )}
                  </div>
                )}

                {/* Title */}
                <div className="mb-6">
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
                    Caption Title
                  </label>
                  {editingContentId === selectedContent.content_id ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-blue-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg font-semibold text-gray-800"
                      placeholder="Enter caption title..."
                    />
                  ) : (
                    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                      <h4 className="text-lg font-semibold text-gray-800">{selectedContent.title}</h4>
                    </div>
                  )}
                </div>

                {/* Body */}
                <div className="mb-6">
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
                    Caption Body
                  </label>
                  {editingContentId === selectedContent.content_id ? (
                    <textarea
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      rows={8}
                      className="w-full px-4 py-3 border-2 border-blue-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-700 whitespace-pre-wrap text-sm leading-relaxed resize-y"
                      placeholder="Enter caption body..."
                    />
                  ) : (
                    <>
                      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 max-h-64 overflow-y-auto">
                        <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                          {selectedContent.body}
                        </p>
                      </div>
                      <button
                        onClick={() => copyToClipboard(selectedContent.body, selectedContent.content_id)}
                        className="mt-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
                      >
                        {copiedId === selectedContent.content_id ? '✓ Copied!' : 'Copy caption to clipboard'}
                      </button>
                    </>
                  )}
                </div>

                {/* Regenerate Panel */}
                {onRegenerate && generationContext && editingContentId !== selectedContent.content_id && (
                  <div className="mb-6 border border-amber-200 bg-amber-50 rounded-lg p-4">
                    {!showRegeneratePanel ? (
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="text-sm font-semibold text-amber-900">Not happy with this caption?</p>
                          <p className="text-xs text-amber-800 mt-0.5">
                            Generate a fresh title and body. Add details to steer the new version.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setShowRegeneratePanel(true);
                            setRegenerateError(null);
                          }}
                          className="shrink-0 px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 transition-colors"
                        >
                          🔄 Regenerate
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div>
                          <p className="text-sm font-semibold text-amber-900 mb-1">Regenerate caption</p>
                          <p className="text-xs text-amber-800">
                            Tell the AI what to change — tone, length, angle, keywords, or anything else.
                          </p>
                        </div>
                        <textarea
                          value={regenerationInstructions}
                          onChange={(e) => setRegenerationInstructions(e.target.value)}
                          rows={4}
                          placeholder="e.g., Make it shorter and more casual. Lead with the EU partnership. Use fewer hashtags and a stronger CTA."
                          className="w-full px-3 py-2 border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm text-gray-800 bg-white"
                        />
                        {regenerateError && (
                          <p className="text-sm text-red-600">{regenerateError}</p>
                        )}
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleRegenerate}
                            disabled={regenerating}
                            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium text-white transition-colors ${
                              regenerating
                                ? 'bg-gray-400 cursor-not-allowed'
                                : 'bg-amber-600 hover:bg-amber-700'
                            }`}
                          >
                            {regenerating ? (
                              <span className="flex items-center justify-center gap-2">
                                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                Generating...
                              </span>
                            ) : (
                              '✨ Generate New Caption'
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setShowRegeneratePanel(false);
                              setRegenerationInstructions('');
                              setRegenerateError(null);
                            }}
                            disabled={regenerating}
                            className="px-4 py-2 rounded-lg text-sm font-medium bg-white border border-amber-300 text-amber-900 hover:bg-amber-100 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Metadata */}
                <div className="space-y-4">
                  {/* Hashtags */}
                  {selectedContent.metadata.hashtags && selectedContent.metadata.hashtags.length > 0 && (
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
                        Hashtags
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {selectedContent.metadata.hashtags.map((tag, idx) => (
                          <span
                            key={idx}
                            className="bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Keywords */}
                  {selectedContent.metadata.keywords && selectedContent.metadata.keywords.length > 0 && (
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
                        Keywords
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {selectedContent.metadata.keywords.map((keyword, idx) => (
                          <span
                            key={idx}
                            className="bg-gray-200 text-gray-800 text-sm px-3 py-1 rounded-full"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Meta info */}
                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-semibold">Tone</p>
                      <p className="text-sm text-gray-800 capitalize">
                        {selectedContent.metadata.tone}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-semibold">Audience</p>
                      <p className="text-sm text-gray-800 capitalize">
                        {selectedContent.metadata.target_audience}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-semibold">Status</p>
                      <span className="inline-block mt-1 px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                        {selectedContent.status}
                      </span>
                    </div>
                    {selectedContent.metadata.call_to_action && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase font-semibold">CTA</p>
                        <p className="text-sm text-gray-800">{selectedContent.metadata.call_to_action}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 mt-6 pt-6 border-t border-gray-200">
                  {editingContentId === selectedContent.content_id ? (
                    <>
                      <button
                        onClick={saveEditing}
                        disabled={!editTitle.trim()}
                        className={`flex-1 py-2 px-4 rounded-lg transition-all font-medium text-sm ${
                          editTitle.trim()
                            ? 'bg-green-600 text-white hover:bg-green-700'
                            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        }`}
                      >
                        💾 Save Changes
                      </button>
                      <button
                        onClick={cancelEditing}
                        className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-all font-medium text-sm"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => copyToClipboard(selectedContent.body, selectedContent.content_id)}
                        className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-all font-medium text-sm"
                      >
                        {copiedId === selectedContent.content_id ? '✓ Copied' : '📋 Copy Caption'}
                      </button>
                      <button
                        onClick={() => startEditing(selectedContent)}
                        className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-all font-medium text-sm"
                      >
                        ✏️ Edit Caption
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
