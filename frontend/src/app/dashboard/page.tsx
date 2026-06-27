'use client';

import { useCallback, useEffect, useState } from 'react';
import { API_ENDPOINTS, apiFetch, fetchWithTimeout } from '@/lib/api-client';
import PostFromDraftPanel from '@/components/dashboard/PostFromDraftPanel';

interface ContentItem {
  id: number;
  platform: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  media_type?: string | null;
  linkedin_post_status?: string;
  facebook_post_status?: string;
  instagram_post_status?: string;
  youtube_post_status?: string;
  linkedin_post_id?: string | null;
  facebook_post_id?: string | null;
  instagram_post_id?: string | null;
  youtube_post_id?: string | null;
}

interface ApprovalStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  pass_rate: number | null;
}

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

const getPlatformPostStatus = (content: ContentItem) => {
  const platformStatusKey = `${content.platform}_post_status` as keyof ContentItem;
  const platformStatus = content[platformStatusKey];
  return String(platformStatus || content.status || 'draft').toLowerCase();
};

const isPosted = (content: ContentItem) => {
  const s = getPlatformPostStatus(content);
  return s === 'published' || s === 'posted';
};

const getDisplayStatus = (content: ContentItem) => {
  const s = getPlatformPostStatus(content);
  return isPosted(content) ? 'published' : s === 'failed' ? 'failed' : 'draft';
};

// Inline confirmation dialog (no external library needed)
function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
        <p className="text-sm text-slate-500 mb-6">{message}</p>
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-lg bg-red-600 text-white font-semibold text-sm hover:bg-red-700 transition-colors"
          >
            {confirmLabel}
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-lg bg-slate-100 text-slate-700 font-semibold text-sm hover:bg-slate-200 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [stats, setStats] = useState({ total: 0, drafted: 0, posted: 0 });
  const [qaStats, setQaStats] = useState<ApprovalStats | null>(null);
  const [clearing, setClearing] = useState(false);

  // Confirmation dialog state
  const [dialog, setDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
  }>({ open: false, title: '', message: '', confirmLabel: '', onConfirm: () => {} });

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    const [contentResult, qaResult] = await Promise.allSettled([
      fetchWithTimeout(API_ENDPOINTS.CONTENT_HISTORY + '?limit=50'),
      fetchWithTimeout(API_ENDPOINTS.APPROVAL_STATS),
    ]);

    if (contentResult.status === 'fulfilled' && contentResult.value.ok) {
      const data: ContentItem[] = await contentResult.value.json();
      setContents(data);
      const posted = data.filter(isPosted).length;
      setStats({ total: data.length, drafted: data.length - posted, posted });
    } else if (contentResult.status === 'rejected') {
      console.error('Failed to fetch content:', contentResult.reason);
    }

    if (qaResult.status === 'fulfilled' && qaResult.value.ok) {
      setQaStats(await qaResult.value.json());
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const clearAll = async () => {
    setClearing(true);
    try {
      const res = await apiFetch(API_ENDPOINTS.CONTENT_CLEAR_ALL, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err.detail === 'string' ? err.detail : 'Failed to clear dashboard data'
        );
      }
      setContents([]);
      setStats({ total: 0, drafted: 0, posted: 0 });
      setQaStats(null);
    } catch (err) {
      console.error('Clear failed:', err);
      alert(err instanceof Error ? err.message : 'Failed to clear dashboard data');
    } finally {
      setClearing(false);
    }
  };

  const clearStats = async () => {
    setClearing(true);
    try {
      const res = await apiFetch(API_ENDPOINTS.CONTENT_CLEAR_STATS, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err.detail === 'string' ? err.detail : 'Failed to clear dashboard stats'
        );
      }
      await loadDashboard();
    } catch (err) {
      console.error('Clear stats failed:', err);
      alert(err instanceof Error ? err.message : 'Failed to clear dashboard stats');
    } finally {
      setClearing(false);
    }
  };

  const openClearContent = () =>
    setDialog({
      open: true,
      title: 'Clear all content?',
      message:
        'This will permanently delete every item in Recent Content & Drafts, including their approval requests. This cannot be undone.',
      confirmLabel: 'Clear Content',
      onConfirm: () => {
        setDialog((d) => ({ ...d, open: false }));
        clearAll();
      },
    });

  const openClearStats = () =>
    setDialog({
      open: true,
      title: 'Clear all stats?',
      message:
        'This will delete content and approval history used for dashboard stats. Items scheduled on the Calendar are kept. This cannot be undone.',
      confirmLabel: 'Clear Stats',
      onConfirm: () => {
        setDialog((d) => ({ ...d, open: false }));
        clearStats();
      },
    });

  const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  // QA Pass Rate display
  const qaPassRate =
    qaStats === null
      ? '—'
      : qaStats.pass_rate === null
      ? 'N/A'
      : `${qaStats.pass_rate}%`;

  const qaColor =
    qaStats?.pass_rate === null || qaStats === null
      ? 'text-slate-700'
      : qaStats.pass_rate >= 75
      ? 'text-emerald-600'
      : qaStats.pass_rate >= 50
      ? 'text-gold-600'
      : 'text-red-600';

  return (
    <div className="space-y-8">
      <ConfirmDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        confirmLabel={dialog.confirmLabel}
        onConfirm={dialog.onConfirm}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
      />

      {/* Stat Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Overview</h2>
          <button
            onClick={openClearStats}
            disabled={clearing || stats.total === 0}
            className="text-xs text-red-500 hover:text-red-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            🗑 Clear Stats
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-500 text-sm font-medium">Total Content</p>
                <p className="text-3xl font-bold text-brand-700 mt-1">{stats.total}</p>
              </div>
              <span className="text-3xl">📊</span>
            </div>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-500 text-sm font-medium">Drafts</p>
                <p className="text-3xl font-bold text-gold-600 mt-1">{stats.drafted}</p>
              </div>
              <span className="text-3xl">📝</span>
            </div>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-500 text-sm font-medium">Posted</p>
                <p className="text-3xl font-bold text-emerald-600 mt-1">{stats.posted}</p>
              </div>
              <span className="text-3xl">🚀</span>
            </div>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-500 text-sm font-medium">QA Pass Rate</p>
                <p className={`text-3xl font-bold mt-1 ${qaColor}`}>{qaPassRate}</p>
                {qaStats && qaStats.approved + qaStats.rejected > 0 && (
                  <p className="text-[11px] text-slate-400 mt-1">
                    {qaStats.approved}✓ {qaStats.rejected}✕{qaStats.pending > 0 ? ` · ${qaStats.pending} pending` : ''}
                  </p>
                )}
              </div>
              <span className="text-3xl">✅</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Content */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">📋 Recent Content & Drafts</h2>
          <div className="flex items-center gap-3">
            {contents.length > 0 && (
              <button
                onClick={openClearContent}
                disabled={clearing}
                className="text-sm text-red-500 hover:text-red-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                🗑 Clear All
              </button>
            )}
            <button
              onClick={loadDashboard}
              className="text-sm text-brand-700 hover:text-brand-800 font-medium"
            >
              ↻ Refresh
            </button>
          </div>
        </div>

        {clearing ? (
          <div className="p-12 text-center">
            <span className="inline-block w-6 h-6 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 mt-2 text-sm">Clearing...</p>
          </div>
        ) : loading ? (
          <div className="p-12 text-center">
            <span className="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 mt-2 text-sm">Loading drafts...</p>
          </div>
        ) : contents.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-4xl mb-3">📭</p>
            <p className="text-gray-500 font-medium">No content yet</p>
            <p className="text-gray-400 text-sm mt-1">
              Generate your first post in the{' '}
              <a href="/dashboard/generator" className="text-brand-700 hover:underline">
                Content Generator
              </a>
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {contents.map((content) => (
              <div key={content.id}>
                <div
                  className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setExpandedId(expandedId === content.id ? null : content.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <span className="text-2xl flex-shrink-0">{PLATFORM_ICONS[content.platform] || '📄'}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {content.title || 'Untitled'}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          <span className="capitalize">{content.platform}</span>
                          {' · '}
                          {formatDate(content.created_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        getDisplayStatus(content) === 'published'
                          ? 'bg-green-100 text-green-800'
                          : getDisplayStatus(content) === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gold-50 text-gold-800 border border-gold-200'
                      }`}>
                        {getDisplayStatus(content)}
                      </span>
                      <span className="text-gray-400 text-sm">
                        {expandedId === content.id ? '▲' : '▼'}
                      </span>
                    </div>
                  </div>
                </div>

                {expandedId === content.id && (
                  <div className="px-6 pb-4 pt-0">
                    <div className="bg-gray-50 rounded-lg p-4 ml-11 border border-gray-200">
                      {content.body ? (
                        <>
                          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                            {content.body}
                          </p>
                          <button
                            onClick={(e) => { e.stopPropagation(); copyToClipboard(content.body); }}
                            className="mt-2 text-xs text-brand-700 hover:text-brand-800 font-medium"
                          >
                            📋 Copy caption
                          </button>
                        </>
                      ) : (
                        <p className="text-sm text-gray-400 italic">No caption body</p>
                      )}
                      {!isPosted(content) && (
                        <PostFromDraftPanel content={content} onPosted={loadDashboard} />
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
