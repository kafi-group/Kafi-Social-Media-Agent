'use client';

import { useCallback, useEffect, useState } from 'react';
import { API_ENDPOINTS } from '@/lib/api-client';
import { ApprovalRequest } from '@/lib/types';

type Tab = 'pending' | 'approved' | 'rejected';

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

function mediaSrc(approval: ApprovalRequest): string | null {
  if (approval.media_url) {
    if (approval.media_url.startsWith('http')) return approval.media_url;
    return `${API_ENDPOINTS.UPLOADS}/${approval.media_url.replace(/^\/?uploads\//, '')}`;
  }
  if (approval.media_path) return `${API_ENDPOINTS.UPLOADS}/${approval.media_path}`;
  return null;
}

export default function QAPage() {
  const [tab, setTab] = useState<Tab>('pending');
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pin, setPin] = useState('');
  const [pinValid, setPinValid] = useState<boolean | null>(null);
  const [verifying, setVerifying] = useState(false);

  const [actioningId, setActioningId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectNote, setRejectNote] = useState('');
  const [pendingCount, setPendingCount] = useState(0);

  const loadApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_ENDPOINTS.APPROVALS}?status=${tab}`);
      if (!res.ok) throw new Error('Failed to load approval requests');
      const data: ApprovalRequest[] = await res.json();
      setApprovals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  const loadPendingCount = useCallback(async () => {
    try {
      const res = await fetch(`${API_ENDPOINTS.APPROVALS}?status=pending`);
      if (res.ok) {
        const data: ApprovalRequest[] = await res.json();
        setPendingCount(data.length);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  useEffect(() => {
    loadPendingCount();
  }, [loadPendingCount, approvals]);

  const verifyPin = async () => {
    if (!pin.trim()) return;
    setVerifying(true);
    try {
      const res = await fetch(API_ENDPOINTS.DESIGNER_VERIFY_PIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      setPinValid(Boolean(data.valid));
    } catch {
      setPinValid(false);
    } finally {
      setVerifying(false);
    }
  };

  const approve = async (id: number) => {
    if (!pin.trim()) {
      setError('Enter the designer PIN first.');
      return;
    }
    setActioningId(id);
    setError(null);
    try {
      const res = await fetch(API_ENDPOINTS.APPROVAL_APPROVE(id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to approve');
      }
      await loadApprovals();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setActioningId(null);
    }
  };

  const reject = async (id: number) => {
    if (!pin.trim()) {
      setError('Enter the designer PIN first.');
      return;
    }
    setActioningId(id);
    setError(null);
    try {
      const res = await fetch(API_ENDPOINTS.APPROVAL_REJECT(id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin, note: rejectNote.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to reject');
      }
      setRejectingId(null);
      setRejectNote('');
      await loadApprovals();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject');
    } finally {
      setActioningId(null);
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'pending', label: `Pending${pendingCount ? ` (${pendingCount})` : ''}` },
    { id: 'approved', label: 'Approved' },
    { id: 'rejected', label: 'Rejected' },
  ];

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">QA Checker</h1>
        <p className="text-slate-500 mt-1">
          Review posts submitted by the team. Approve to publish, or reject to block.
        </p>
      </div>

      {/* Designer PIN */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 mb-6">
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          Designer PIN
        </label>
        <p className="text-xs text-slate-500 mb-3">
          Required to approve or reject posts. This confirms you are the designer.
        </p>
        <div className="flex gap-2 flex-wrap items-center">
          <input
            type="password"
            value={pin}
            onChange={(e) => {
              setPin(e.target.value);
              setPinValid(null);
            }}
            placeholder="Enter designer PIN"
            className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm w-64"
          />
          <button
            onClick={verifyPin}
            disabled={verifying || !pin.trim()}
            className="px-4 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-900 disabled:bg-slate-300 disabled:cursor-not-allowed"
          >
            {verifying ? 'Checking...' : 'Verify'}
          </button>
          {pinValid === true && (
            <span className="text-sm text-green-700 font-medium">✓ PIN verified</span>
          )}
          {pinValid === false && (
            <span className="text-sm text-red-600 font-medium">✕ Invalid PIN</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm py-12 text-center">Loading...</div>
      ) : approvals.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-10 text-center">
          <p className="text-slate-500">
            {tab === 'pending'
              ? 'No posts are waiting for approval.'
              : `No ${tab} posts.`}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((a) => {
            const src = mediaSrc(a);
            return (
              <div
                key={a.id}
                className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden"
              >
                <div className="flex flex-col md:flex-row">
                  {/* Media */}
                  <div className="md:w-56 bg-slate-50 flex-shrink-0 flex items-center justify-center p-3">
                    {src && a.media_type === 'video' ? (
                      <video src={src} controls className="w-full max-h-48 rounded-lg object-contain" />
                    ) : src ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt="Post media" className="w-full max-h-48 rounded-lg object-contain" />
                    ) : (
                      <div className="text-slate-400 text-sm py-12">No media</div>
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 p-5">
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <span className="text-xl">{PLATFORM_ICONS[a.platform || ''] || '📝'}</span>
                      <span className="text-sm font-semibold text-slate-800 capitalize">
                        {a.platform || 'post'}
                      </span>
                      <span className="text-xs text-slate-400">·</span>
                      <span className="text-xs text-slate-500">
                        {a.requested_by || 'A team member'}
                      </span>
                      <span className="text-xs text-slate-400">·</span>
                      <span className="text-xs text-slate-500">
                        {new Date(a.created_at).toLocaleString()}
                      </span>
                      {a.draft_mode && (
                        <span className="text-[10px] uppercase font-bold bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full">
                          Draft mode
                        </span>
                      )}
                    </div>

                    <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1">
                      Head caption
                    </p>
                    <h3 className="text-base font-semibold text-slate-900 mb-3">{a.title}</h3>

                    <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1">
                      Body caption
                    </p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap max-h-40 overflow-y-auto mb-4">
                      {a.body}
                    </p>

                    {a.platforms && a.platforms.length > 0 && (
                      <p className="text-xs text-slate-500 mb-4">
                        Will publish to:{' '}
                        <span className="font-medium text-slate-700 capitalize">
                          {a.platforms.join(', ')}
                        </span>
                      </p>
                    )}

                    {/* Rejected note */}
                    {a.status === 'rejected' && a.reviewer_note && (
                      <div className="mb-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
                        {a.reviewer_note}
                      </div>
                    )}

                    {/* Approved results */}
                    {a.status === 'approved' && a.results && (
                      <div className="mb-2 space-y-1">
                        {a.results.map((r, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            <span className="capitalize text-slate-600">{r.platform}</span>
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                r.status === 'published'
                                  ? 'bg-green-100 text-green-800'
                                  : r.status === 'draft'
                                  ? 'bg-yellow-100 text-yellow-800'
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
                                className="text-blue-600 hover:underline text-xs"
                              >
                                View ↗
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Actions (pending only) */}
                    {a.status === 'pending' && (
                      <div className="pt-2">
                        {rejectingId === a.id ? (
                          <div className="space-y-2">
                            <textarea
                              value={rejectNote}
                              onChange={(e) => setRejectNote(e.target.value)}
                              rows={2}
                              placeholder="Reason for rejection (optional)"
                              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() => reject(a.id)}
                                disabled={actioningId === a.id}
                                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:bg-slate-300"
                              >
                                {actioningId === a.id ? 'Rejecting...' : 'Confirm Reject'}
                              </button>
                              <button
                                onClick={() => {
                                  setRejectingId(null);
                                  setRejectNote('');
                                }}
                                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => approve(a.id)}
                              disabled={actioningId === a.id}
                              className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:bg-slate-300"
                            >
                              {actioningId === a.id ? 'Approving...' : '✓ Approve & Post'}
                            </button>
                            <button
                              onClick={() => {
                                setRejectingId(a.id);
                                setRejectNote('');
                              }}
                              disabled={actioningId === a.id}
                              className="px-4 py-2 rounded-lg bg-white border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50"
                            >
                              ✕ Reject
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
