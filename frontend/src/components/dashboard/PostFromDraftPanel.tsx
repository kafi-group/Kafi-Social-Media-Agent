'use client';

import { useEffect, useState } from 'react';
import { API_ENDPOINTS, apiFetch } from '@/lib/api-client';
import { LinkedInAccountInfo, SocialPostResponse } from '@/lib/types';
import SocialPlatformIcon, { SOCIAL_PLATFORMS } from '@/components/icons/SocialPlatformIcon';

const POSTABLE_PLATFORMS = SOCIAL_PLATFORMS.filter((p) =>
  ['linkedin', 'facebook', 'instagram', 'youtube'].includes(p.id),
);

interface DraftContent {
  id: number;
  platform: string;
  title: string;
  body: string;
}

interface PostFromDraftPanelProps {
  content: DraftContent;
  onPosted: () => void;
}

export default function PostFromDraftPanel({ content, onPosted }: PostFromDraftPanelProps) {
  const defaultPlatform = POSTABLE_PLATFORMS.some((p) => p.id === content.platform)
    ? [content.platform]
    : ['linkedin'];

  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(defaultPlatform);
  const [linkedinAccounts, setLinkedinAccounts] = useState<LinkedInAccountInfo[]>([]);
  const [selectedLinkedinAccounts, setSelectedLinkedinAccounts] = useState<string[]>([]);
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [designerPin, setDesignerPin] = useState('');
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SocialPostResponse[]>([]);

  useEffect(() => {
    setSelectedPlatforms(defaultPlatform);
    setResults([]);
    setError(null);
    setDesignerPin('');
  }, [content.id, content.platform]);

  useEffect(() => {
    apiFetch(API_ENDPOINTS.APPROVAL_CONFIG)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setApprovalRequired(Boolean(data?.approval_required)))
      .catch(() => setApprovalRequired(false));

    apiFetch(API_ENDPOINTS.LINKEDIN_ACCOUNTS)
      .then((res) => (res.ok ? res.json() : []))
      .then((accounts: LinkedInAccountInfo[]) => {
        setLinkedinAccounts(accounts);
        setSelectedLinkedinAccounts(accounts.map((a) => a.label));
      })
      .catch(() => {
        setLinkedinAccounts([]);
        setSelectedLinkedinAccounts([]);
      });
  }, []);

  const togglePlatform = (platformId: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platformId) ? prev.filter((p) => p !== platformId) : [...prev, platformId],
    );
  };

  const toggleLinkedinAccount = (label: string) => {
    setSelectedLinkedinAccounts((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label],
    );
  };

  const handlePost = async () => {
    if (selectedPlatforms.length === 0) {
      setError('Select at least one platform to post to.');
      return;
    }

    if (
      selectedPlatforms.includes('linkedin') &&
      linkedinAccounts.length > 0 &&
      selectedLinkedinAccounts.length === 0
    ) {
      setError('Select at least one LinkedIn account.');
      return;
    }

    if (approvalRequired && !designerPin.trim()) {
      setError('Designer PIN is required to publish from drafts.');
      return;
    }

    setPosting(true);
    setError(null);
    setResults([]);

    try {
      const payload: Record<string, unknown> = {
        content_id: content.id,
        platforms: selectedPlatforms,
        draft_mode: false,
      };

      if (approvalRequired) {
        payload.designer_pin = designerPin.trim();
      }

      if (selectedPlatforms.includes('linkedin') && selectedLinkedinAccounts.length > 0) {
        payload.linkedin_account_labels = selectedLinkedinAccounts;
      }

      const res = await apiFetch(API_ENDPOINTS.SOCIAL_POST(content.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to post');
      }

      const postResults: SocialPostResponse[] = await res.json();
      setResults(postResults);

      const anyPublished = postResults.some((r) => r.status === 'published');
      if (anyPublished) {
        onPosted();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to post');
    } finally {
      setPosting(false);
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-gray-200">
      <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Post from draft</p>
      <p className="text-xs text-slate-500 mb-3">
        Choose platforms and publish this caption live to social media.
      </p>

      <div className="flex flex-wrap gap-2 mb-3">
        {POSTABLE_PLATFORMS.map((p) => {
          const selected = selectedPlatforms.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                togglePlatform(p.id);
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                selected
                  ? 'border-brand-600 bg-brand-50 text-brand-800'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
              }`}
            >
              <SocialPlatformIcon platform={p.id} size={14} />
              {p.name}
            </button>
          );
        })}
      </div>

      {selectedPlatforms.includes('linkedin') && linkedinAccounts.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-600 mb-1.5">LinkedIn accounts</p>
          <div className="flex flex-wrap gap-2">
            {linkedinAccounts.map((account) => (
              <label
                key={account.label}
                className="inline-flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  checked={selectedLinkedinAccounts.includes(account.label)}
                  onChange={() => toggleLinkedinAccount(account.label)}
                  className="rounded border-slate-300"
                />
                {account.label}
              </label>
            ))}
          </div>
        </div>
      )}

      {approvalRequired && (
        <div className="mb-3" onClick={(e) => e.stopPropagation()}>
          <label className="block text-xs font-medium text-slate-600 mb-1">Designer PIN</label>
          <input
            type="password"
            value={designerPin}
            onChange={(e) => setDesignerPin(e.target.value)}
            placeholder="Required to publish"
            className="w-full max-w-xs px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 mb-2">{error}</p>
      )}

      {results.length > 0 && (
        <div className="mb-3 space-y-1">
          {results.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="capitalize text-slate-600">{r.platform}</span>
              {r.account_label && (
                <span className="text-slate-400">({r.account_label})</span>
              )}
              <span
                className={`px-2 py-0.5 rounded font-semibold ${
                  r.status === 'published'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {r.status}
              </span>
              {r.post_url && (
                <a
                  href={r.post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-700 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  View ↗
                </a>
              )}
              {r.error_message && (
                <span className="text-red-600 truncate max-w-[200px]">{r.error_message}</span>
              )}
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          handlePost();
        }}
        disabled={posting || selectedPlatforms.length === 0}
        className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
      >
        {posting ? 'Publishing...' : '🚀 Post Live'}
      </button>
    </div>
  );
}
