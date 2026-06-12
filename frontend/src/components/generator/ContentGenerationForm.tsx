'use client';

import { useState, useRef, useEffect } from 'react';
import { ContentGenerationResponse, ContentRegenerateRequest, LinkedInAccountInfo, SocialPostResponse } from '@/lib/types';
import { API_ENDPOINTS, API_CONFIG } from '@/lib/api-client';
import GeneratedContentDisplay from './GeneratedContentDisplay';
import DesignerGateModal from './DesignerGateModal';
import ScheduleModal from '@/components/calendar/ScheduleModal';

interface ContentGenerationFormProps {
  onGenerate?: (results: ContentGenerationResponse[]) => void;
}

const PLATFORMS = [
  { id: 'linkedin', name: 'LinkedIn', icon: '💼' },
  { id: 'facebook', name: 'Facebook', icon: '👍' },
  { id: 'instagram', name: 'Instagram', icon: '📷' },
  { id: 'twitter', name: 'Twitter/X', icon: '𝕏' },
  { id: 'tiktok', name: 'TikTok', icon: '🎵' },
  { id: 'youtube', name: 'YouTube', icon: '▶️' },
];

const TONES = [
  'professional',
  'casual',
  'humorous',
  'inspirational',
  'educational',
  'persuasive',
  'friendly',
];

const AUDIENCES = ['business', 'consumer', 'general', 'youth', 'enterprise'];

export default function ContentGenerationForm({ onGenerate }: ContentGenerationFormProps) {
  // Form state
  const [step, setStep] = useState<'input' | 'preview'>('input');
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(['linkedin', 'facebook']);
  const [topic, setTopic] = useState('');
  const [brandContext, setBrandContext] = useState('Kafi Commodities');
  const [tone, setTone] = useState('professional');
  const [targetAudience, setTargetAudience] = useState('business');
  const [callToAction, setCallToAction] = useState('');
  const [additionalInstructions, setAdditionalInstructions] = useState('');

  // Media state
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<'image' | 'video' | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Generation state
  const [generatedContents, setGeneratedContents] = useState<ContentGenerationResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [postingStates, setPostingStates] = useState<Record<string, 'idle' | 'posting' | 'done' | 'error' | 'partial'>>({});
  const [postResults, setPostResults] = useState<SocialPostResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [draftMode, setDraftMode] = useState(true); // Start in draft/test mode by default

  // LinkedIn multi-account selection
  const [linkedinAccounts, setLinkedinAccounts] = useState<LinkedInAccountInfo[]>([]);
  const [selectedLinkedinAccounts, setSelectedLinkedinAccounts] = useState<string[]>([]);
  const [loadingLinkedinAccounts, setLoadingLinkedinAccounts] = useState(false);

  // Track edited captions from preview (keyed by content_id)
  const [editedContents, setEditedContents] = useState<Record<number, { title: string; body: string }>>({});

  // Scheduling
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleContentId, setScheduleContentId] = useState<number | null>(null);

  // Designer approval gate
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [emailConfigured, setEmailConfigured] = useState(false);
  const [gateOpen, setGateOpen] = useState(false);
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [approvalSubmitted, setApprovalSubmitted] = useState(false);

  const handleContentUpdate = (contentId: number, updatedTitle: string, updatedBody: string) => {
    setEditedContents((prev) => ({
      ...prev,
      [contentId]: { title: updatedTitle, body: updatedBody },
    }));
    setGeneratedContents((prev) =>
      prev.map((c) =>
        c.content_id === contentId ? { ...c, title: updatedTitle, body: updatedBody } : c
      )
    );
  };

  const handleRegenerate = async (
    contentId: number,
    payload: ContentRegenerateRequest
  ): Promise<ContentGenerationResponse> => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), API_CONFIG.timeout);

    let response: Response;
    try {
      response = await fetch(API_ENDPOINTS.CONTENT_REGENERATE(contentId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new Error(
          'Caption regeneration timed out. The AI took too long — try again with shorter instructions.'
        );
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const detail = errorData.detail;
      if (response.status === 404 && detail === 'Not Found') {
        throw new Error(
          'Regenerate is not available on the running backend. Stop the server completely and start it again, then retry.'
        );
      }
      if (response.status === 504) {
        throw new Error(
          typeof detail === 'string'
            ? detail
            : 'AI service timed out while regenerating. Please try again.'
        );
      }
      throw new Error(
        typeof detail === 'string' ? detail : 'Failed to regenerate caption'
      );
    }

    const updated: ContentGenerationResponse = await response.json();

    setGeneratedContents((prev) =>
      prev.map((c) => (c.content_id === contentId ? updated : c))
    );
    setEditedContents((prev) => {
      const next = { ...prev };
      delete next[contentId];
      return next;
    });

    return updated;
  };

  // Cleanup object URL on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (mediaPreview) URL.revokeObjectURL(mediaPreview);
    };
  }, [mediaPreview]);

  // Load approval config (whether posts must be approved by the designer)
  useEffect(() => {
    let cancelled = false;
    fetch(API_ENDPOINTS.APPROVAL_CONFIG)
      .then((res) => (res.ok ? res.json() : null))
      .then((cfg) => {
        if (cancelled || !cfg) return;
        setApprovalRequired(Boolean(cfg.approval_required));
        setEmailConfigured(Boolean(cfg.designer_email_configured));
      })
      .catch(() => {
        /* gate stays off if config can't load */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load configured LinkedIn accounts when entering preview step
  useEffect(() => {
    if (step !== 'preview' || !selectedPlatforms.includes('linkedin')) return;

    let cancelled = false;
    setLoadingLinkedinAccounts(true);

    fetch(API_ENDPOINTS.LINKEDIN_ACCOUNTS)
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load LinkedIn accounts');
        return res.json() as Promise<LinkedInAccountInfo[]>;
      })
      .then((accounts) => {
        if (cancelled) return;
        setLinkedinAccounts(accounts);
        setSelectedLinkedinAccounts(accounts.map((a) => a.label));
      })
      .catch(() => {
        if (!cancelled) {
          setLinkedinAccounts([]);
          setSelectedLinkedinAccounts([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingLinkedinAccounts(false);
      });

    return () => {
      cancelled = true;
    };
  }, [step, selectedPlatforms]);

  const handleLinkedinAccountToggle = (label: string) => {
    setSelectedLinkedinAccounts((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    );
  };

  const handlePlatformToggle = (platformId: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platformId) ? prev.filter((p) => p !== platformId) : [...prev, platformId]
    );
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');

    if (!isImage && !isVideo) {
      setError('Please select an image or video file (JPG, PNG, GIF, MP4, MOV, etc.)');
      return;
    }

    setMediaFile(file);
    setMediaType(isImage ? 'image' : 'video');
    setError(null);

    // Create preview URL
    const previewUrl = URL.createObjectURL(file);
    setMediaPreview(previewUrl);
  };

  const handleRemoveMedia = () => {
    if (mediaPreview) URL.revokeObjectURL(mediaPreview);
    setMediaFile(null);
    setMediaPreview(null);
    setMediaType(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (selectedPlatforms.length === 0) {
      setError('Please select at least one platform to post to');
      return;
    }

    if (!topic.trim()) {
      setError('Please enter a topic for the AI to write about');
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('platforms', JSON.stringify(selectedPlatforms));
      formData.append('topic', topic.trim());
      formData.append('brand_context', brandContext);
      formData.append('tone', tone);
      formData.append('target_audience', targetAudience);
      formData.append('call_to_action', callToAction);
      formData.append('additional_instructions', additionalInstructions);

      if (mediaFile) {
        formData.append('media_file', mediaFile);
      }

      const response = await fetch(API_ENDPOINTS.CONTENT_GENERATE_WITH_MEDIA, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to generate content');
      }

      const results: ContentGenerationResponse[] = await response.json();
      setGeneratedContents(results);
      setStep('preview');
      onGenerate?.(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Validate the post selection. Returns the platforms to post to, or null.
  const validatePost = (): string[] | null => {
    const platformsToPost = selectedPlatforms.filter(p => ['linkedin', 'facebook', 'instagram', 'youtube'].includes(p));

    if (platformsToPost.length === 0) {
      setError('Select at least LinkedIn, Facebook, Instagram, or YouTube to post');
      return null;
    }

    if (
      platformsToPost.includes('linkedin') &&
      linkedinAccounts.length > 0 &&
      selectedLinkedinAccounts.length === 0
    ) {
      setError('Select at least one LinkedIn account to post to');
      return null;
    }
    return platformsToPost;
  };

  // Entry point for the "Post Now" button. Shows the designer gate when
  // approval is required, otherwise posts directly.
  const handlePostClick = () => {
    const platformsToPost = validatePost();
    if (!platformsToPost) return;
    setError(null);
    setApprovalSubmitted(false);

    if (approvalRequired) {
      setGateOpen(true);
    } else {
      doPost();
    }
  };

  // Submit the generated posts to the designer for approval (non-designer path).
  const submitForApproval = async (requestedBy: string) => {
    const platformsToPost = validatePost();
    if (!platformsToPost) {
      setGateOpen(false);
      return;
    }

    setSubmittingApproval(true);
    setError(null);

    try {
      for (const content of generatedContents) {
        if (!platformsToPost.includes(content.platform)) continue;

        const edited = editedContents[content.content_id];
        const payload: Record<string, unknown> = {
          content_id: content.content_id,
          platforms: [content.platform],
          draft_mode: draftMode,
          override_title: edited?.title ?? null,
          override_body: edited?.body ?? null,
          requested_by: requestedBy || null,
        };
        if (content.platform === 'linkedin' && selectedLinkedinAccounts.length > 0) {
          payload.linkedin_account_labels = selectedLinkedinAccounts;
        }

        const res = await fetch(API_ENDPOINTS.APPROVALS, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'Failed to submit for approval');
        }
      }
      setApprovalSubmitted(true);
      setGateOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit for approval');
    } finally {
      setSubmittingApproval(false);
    }
  };

  const doPost = async (designerPin?: string) => {
    const platformsToPost = validatePost();
    if (!platformsToPost) return;

    setGateOpen(false);

    // Initialize posting states
    const states: Record<string, 'idle' | 'posting' | 'done' | 'error' | 'partial'> = {};
    platformsToPost.forEach(p => { states[p] = 'posting'; });
    setPostingStates(states);
    setPostResults([]);
    setError(null);

    const allResults: SocialPostResponse[] = [];

    // Post each platform-specific content to its matching platform only
    for (const content of generatedContents) {
      // Only post this content to its own platform (e.g., LinkedIn content only goes to LinkedIn)
      if (!platformsToPost.includes(content.platform)) continue;

      // Check if this content was edited in preview
      const edited = editedContents[content.content_id];

      try {
        const postPayload: Record<string, unknown> = {
          content_id: content.content_id,
          platforms: [content.platform],
          draft_mode: draftMode,
          override_title: edited?.title ?? null,
          override_body: edited?.body ?? null,
        };

        if (designerPin) {
          postPayload.designer_pin = designerPin;
        }

        if (content.platform === 'linkedin' && selectedLinkedinAccounts.length > 0) {
          postPayload.linkedin_account_labels = selectedLinkedinAccounts;
        }

        const response = await fetch(API_ENDPOINTS.SOCIAL_POST(content.content_id), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(postPayload),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Post failed');
        }

        const results: SocialPostResponse[] = await response.json();
        allResults.push(...results);

        if (content.platform === 'linkedin' && results.length > 0) {
          const allOk = results.every((r) => r.status === 'published' || r.status === 'draft');
          const allFail = results.every((r) => r.status === 'failed');
          setPostingStates((prev) => ({
            ...prev,
            linkedin: allOk ? 'done' : allFail ? 'error' : 'partial',
          }));
        } else {
          const result = results[0];
          setPostingStates((prev) => ({
            ...prev,
            [content.platform]:
              result?.status === 'published' || result?.status === 'draft' ? 'done' : 'error',
          }));
        }
      } catch (err) {
        allResults.push({
          content_id: content.content_id,
          platform: content.platform,
          status: 'failed',
          error_message: err instanceof Error ? err.message : 'Post failed',
        });
        setPostingStates(prev => ({ ...prev, [content.platform]: 'error' }));
      }
    }

    setPostResults(allResults);
  };

  const handleBackToInput = () => {
    setStep('input');
    setPostResults([]);
    setPostingStates({});
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Preview mode
  if (step === 'preview') {
    return (
      <div className="space-y-8">
        {/* Generated content with media */}
        <GeneratedContentDisplay
          contents={generatedContents}
          mediaPreview={mediaPreview}
          mediaType={mediaType}
          mediaFileName={mediaFile?.name}
          generationContext={{
            topic: topic.trim(),
            brand_context: brandContext,
            tone,
            target_audience: targetAudience,
            call_to_action: callToAction,
            additional_instructions: additionalInstructions,
          }}
          onContentUpdate={handleContentUpdate}
          onRegenerate={handleRegenerate}
        />

        {/* Post to Socials Section */}
        <div className="bg-white rounded-lg shadow-md p-8">
          <h2 className="text-xl font-semibold text-slate-900 mb-2">📤 Post to Social Media</h2>
          <p className="text-sm text-gray-500 mb-6">
            The graphic designer&apos;s media and AI-generated caption will be posted together.
          </p>

          {/* Draft Mode Toggle */}
          <div className="flex items-center gap-3 mb-6 bg-gold-50 border border-gold-200 rounded-lg p-4">
            <button
              type="button"
              onClick={() => setDraftMode(!draftMode)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                draftMode ? 'bg-gold-500' : 'bg-emerald-500'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                draftMode ? 'translate-x-1' : 'translate-x-6'
              }`} />
            </button>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-900">
                {draftMode ? '🔒 Draft Mode (Simulated Posting)' : '🌐 Live Mode (Actual Posting)'}
              </p>
              <p className="text-xs text-slate-600 mt-0.5">
                {draftMode
                  ? 'No API calls made. Configure social keys in Settings for live posting.'
                  : 'Will post live to your connected social media accounts.'}
              </p>
            </div>
          </div>

          {/* Platform selection for posting */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Post to these platforms:
            </label>
            <div className="flex flex-wrap gap-3">
              {['linkedin', 'facebook', 'instagram', 'youtube'].map((pid) => {
                const platform = PLATFORMS.find(p => p.id === pid);
                if (!platform) return null;
                const state = postingStates[pid] || 'idle';
                return (
                  <div
                    key={pid}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 ${
                      selectedPlatforms.includes(pid)
                        ? 'border-green-400 bg-green-50'
                        : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <span className="text-lg">{platform.icon}</span>
                    <span className="text-sm font-medium text-gray-700">{platform.name}</span>
                    {pid === 'linkedin' && linkedinAccounts.length > 0 && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-semibold">
                        {selectedLinkedinAccounts.length}/{linkedinAccounts.length} accounts
                      </span>
                    )}
                    {state === 'posting' && (
                      <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    )}
                    {state === 'done' && <span className="text-green-600 text-sm font-bold">✓</span>}
                    {state === 'partial' && <span className="text-amber-600 text-sm font-bold">~</span>}
                    {state === 'error' && <span className="text-red-600 text-sm font-bold">✗</span>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* LinkedIn account picker */}
          {selectedPlatforms.includes('linkedin') && (
            <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-900">
                  💼 LinkedIn Accounts
                </h3>
                {linkedinAccounts.length > 1 && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedLinkedinAccounts(linkedinAccounts.map((a) => a.label))}
                      className="text-xs text-blue-700 hover:underline"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedLinkedinAccounts([])}
                      className="text-xs text-blue-700 hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              {loadingLinkedinAccounts ? (
                <p className="text-sm text-gray-500">Loading LinkedIn accounts...</p>
              ) : linkedinAccounts.length === 0 ? (
                <p className="text-sm text-amber-700">
                  No LinkedIn accounts configured. Add tokens and person IDs in backend <code className="text-xs">.env</code>.
                </p>
              ) : (
                <>
                  <p className="text-xs text-gray-600 mb-3">
                    Choose which personal profiles to post from. Each account uses its own access token.
                  </p>
                  <div className="space-y-2">
                    {linkedinAccounts.map((account) => (
                      <label
                        key={account.label}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedLinkedinAccounts.includes(account.label)
                            ? 'border-blue-400 bg-white'
                            : 'border-gray-200 bg-gray-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedLinkedinAccounts.includes(account.label)}
                          onChange={() => handleLinkedinAccountToggle(account.label)}
                          className="w-4 h-4 text-blue-600 rounded"
                        />
                        <div className="flex-1">
                          <span className="text-sm font-medium text-gray-800">{account.label}</span>
                          <span className="text-xs text-gray-500 ml-2">Account {account.index}</span>
                        </div>
                        <span className="text-xs text-green-700 font-medium">Connected</span>
                      </label>
                    ))}
                  </div>
                  {selectedLinkedinAccounts.length > 0 && (
                    <p className="text-xs text-blue-800 mt-3 font-medium">
                      Will post to: {selectedLinkedinAccounts.join(', ')}
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {/* Post results */}
          {postResults.length > 0 && (
            <div className="mb-6 bg-gray-50 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-semibold text-gray-700">Posting Results:</h3>

              {/* Non-LinkedIn results */}
              {postResults
                .filter((r) => r.platform !== 'linkedin')
                .map((result, idx) => (
                  <div key={`other-${idx}`} className="flex items-center justify-between text-sm gap-2">
                    <span className="font-medium shrink-0 capitalize">{result.platform}</span>
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold shrink-0 ${
                        result.status === 'published'
                          ? 'bg-green-100 text-green-800'
                          : result.status === 'draft'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {result.status}
                      </span>
                      {result.error_message && (
                        <span className="text-xs text-red-600 truncate max-w-[200px]">
                          {result.error_message}
                        </span>
                      )}
                      {result.post_url && (
                        <a href={result.post_url} target="_blank" rel="noopener noreferrer"
                           className="text-blue-600 hover:underline text-xs shrink-0">
                          View ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}

              {/* LinkedIn results grouped */}
              {postResults.some((r) => r.platform === 'linkedin') && (
                <div className="border border-blue-100 rounded-lg bg-white p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-800">LinkedIn</span>
                    <span className="text-xs text-gray-500">
                      {postResults.filter((r) => r.platform === 'linkedin' && (r.status === 'published' || r.status === 'draft')).length}
                      {' / '}
                      {postResults.filter((r) => r.platform === 'linkedin').length} accounts succeeded
                    </span>
                  </div>
                  {postResults
                    .filter((r) => r.platform === 'linkedin')
                    .map((result, idx) => (
                      <div key={`li-${idx}`} className="flex items-center justify-between text-sm gap-2 pl-2 border-l-2 border-blue-200">
                        <span className="font-medium shrink-0 text-gray-700">
                          {result.account_label || `Account ${idx + 1}`}
                        </span>
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold shrink-0 ${
                            result.status === 'published'
                              ? 'bg-green-100 text-green-800'
                              : result.status === 'draft'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {result.status}
                          </span>
                          {result.error_message && (
                            <span className="text-xs text-red-600 truncate max-w-[200px]">
                              {result.error_message}
                            </span>
                          )}
                          {result.post_url && (
                            <a href={result.post_url} target="_blank" rel="noopener noreferrer"
                               className="text-blue-600 hover:underline text-xs shrink-0">
                              View ↗
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* Approval submitted confirmation */}
          {approvalSubmitted && (
            <div className="mb-4 bg-blue-50 border border-blue-200 text-blue-800 rounded-lg px-4 py-3">
              <p className="font-semibold">Sent to the designer for approval ✅</p>
              <p className="text-sm mt-0.5">
                This post won&apos;t be published until the designer approves it
                {emailConfigured ? ' (an email was sent to them)' : ''}. You can track
                its status in the QA Checker.
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 flex-wrap">
            <button
              onClick={handlePostClick}
              disabled={Object.values(postingStates).some(s => s === 'posting')}
              className={`flex-1 min-w-[180px] py-3 px-4 rounded-lg font-semibold text-white transition-all ${
                Object.values(postingStates).some(s => s === 'posting')
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700'
              }`}
            >
              {Object.values(postingStates).some(s => s === 'posting')
                ? 'Posting...'
                : postResults.length > 0
                ? 'Retry Posting'
                : '📤 Post Now'}
            </button>
            <button
              onClick={() => {
                setScheduleContentId(generatedContents[0]?.content_id ?? null);
                setScheduleOpen(true);
              }}
              className="flex-1 min-w-[180px] py-3 px-4 rounded-lg font-semibold text-white bg-brand-700 hover:bg-brand-800 transition-all"
            >
              🗓️ Schedule for Later
            </button>
            <button
              onClick={handleBackToInput}
              className="px-6 py-3 rounded-lg font-semibold text-gray-700 bg-gray-200 hover:bg-gray-300 transition-all"
            >
              ← Back & Edit
            </button>
          </div>

          <ScheduleModal
            open={scheduleOpen}
            onClose={() => setScheduleOpen(false)}
            onScheduled={() => setScheduleOpen(false)}
            initialContentId={scheduleContentId}
            initialOverrides={
              scheduleContentId != null ? editedContents[scheduleContentId] : undefined
            }
          />

          <DesignerGateModal
            open={gateOpen}
            emailConfigured={emailConfigured}
            submitting={submittingApproval}
            onClose={() => setGateOpen(false)}
            onConfirmDesigner={(pin) => doPost(pin)}
            onSubmitApproval={(requestedBy) => submitForApproval(requestedBy)}
          />

          <p className="text-xs text-gray-400 mt-3 text-center">
            Toggle Draft/Live mode above. Configure social API keys in .env for live posting.
          </p>
        </div>
      </div>
    );
  }

  // Input mode
  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <form onSubmit={handleGenerate} className="space-y-6">
        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Step 1: Upload Media (from Graphic Designer) */}
        <div className="bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-dashed border-purple-300 rounded-xl p-6">
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            🖼️ Step 1: Upload Media from Graphic Designer
          </label>
          <p className="text-xs text-gray-500 mb-4">
            Upload the image or video your graphic designer created. This will be posted alongside the AI-generated caption.
          </p>

          {!mediaPreview ? (
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-purple-400 hover:bg-purple-50/50 transition-all"
            >
              <div className="text-4xl mb-2">📁</div>
              <p className="text-sm font-medium text-gray-600">
                Click to upload image or video
              </p>
              <p className="text-xs text-gray-500 mt-1">
                JPG, PNG, GIF, MP4, MOV (max 50MB)
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>
          ) : (
            <div className="relative">
              {mediaType === 'image' ? (
                <img
                  src={mediaPreview}
                  alt="Preview"
                  className="max-h-64 rounded-lg mx-auto object-contain"
                />
              ) : (
                <video
                  src={mediaPreview}
                  className="max-h-64 rounded-lg mx-auto"
                  controls
                />
              )}
              <div className="flex items-center justify-between mt-3 bg-gray-50 rounded-lg px-4 py-2">
                <span className="text-sm text-gray-600 truncate max-w-[250px]">
                  {mediaFile?.name}
                </span>
                <span className="text-xs text-gray-500">
                  {mediaFile ? formatFileSize(mediaFile.size) : ''}
                </span>
                <button
                  type="button"
                  onClick={handleRemoveMedia}
                  className="text-red-500 hover:text-red-700 text-sm font-medium ml-2"
                >
                  Remove
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Step 2: AI Caption Settings */}
        <div className="border-t border-gray-200 pt-6">
          <label className="block text-sm font-semibold text-gray-700 mb-4">
            ✍️ Step 2: Generate AI Caption
          </label>

          {/* Platform Selection */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Post to Platforms *
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {PLATFORMS.map((platform) => (
                <button
                  key={platform.id}
                  type="button"
                  onClick={() => handlePlatformToggle(platform.id)}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    selectedPlatforms.includes(platform.id)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <div className="text-2xl mb-1">{platform.icon}</div>
                  <div className="text-sm font-medium text-gray-700">{platform.name}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Topic */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Content Topic *
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., 'New sustainable rice export partnership with EU buyers'"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-sm text-gray-500">What should the AI write the caption about?</p>
          </div>

          {/* Brand Context */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Brand Context
            </label>
            <input
              type="text"
              value={brandContext}
              onChange={(e) => setBrandContext(e.target.value)}
              placeholder="Kafi Commodities"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Tone and Audience */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Tone</label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {TONES.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Target Audience</label>
              <select
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {AUDIENCES.map((a) => (
                  <option key={a} value={a}>
                    {a.charAt(0).toUpperCase() + a.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Call to Action */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Call to Action (Optional)
            </label>
            <input
              type="text"
              value={callToAction}
              onChange={(e) => setCallToAction(e.target.value)}
              placeholder="e.g., 'Contact our team for bulk pricing'"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Additional Instructions */}
          <div className="mb-4">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Additional Instructions (Optional)
            </label>
            <textarea
              value={additionalInstructions}
              onChange={(e) => setAdditionalInstructions(e.target.value)}
              placeholder="Specific keywords, style notes, or brand messaging..."
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Generate Button */}
        <button
          type="submit"
          disabled={loading}
          className={`w-full py-3 px-4 rounded-lg font-semibold text-white transition-all ${
            loading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-brand-700 hover:bg-brand-800'
          }`}
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <span className="animate-spin inline-block w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full"></span>
              ✨ Generating Captions...
            </span>
          ) : (
            '✨ Generate Captions & Preview'
          )}
        </button>

        <p className="text-xs text-gray-500 text-center">
          AI generates the caption text. Your media file is attached for posting.
        </p>
      </form>
    </div>
  );
}
