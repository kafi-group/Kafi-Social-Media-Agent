'use client';

import { useState } from 'react';
import { API_ENDPOINTS } from '@/lib/api-client';

interface DesignerGateModalProps {
  open: boolean;
  emailConfigured: boolean;
  submitting: boolean;
  onClose: () => void;
  onConfirmDesigner: (pin: string) => void;
  onSubmitApproval: (requestedBy: string) => void;
}

type Mode = 'choose' | 'designer' | 'requester';

export default function DesignerGateModal({
  open,
  emailConfigured,
  submitting,
  onClose,
  onConfirmDesigner,
  onSubmitApproval,
}: DesignerGateModalProps) {
  const [mode, setMode] = useState<Mode>('choose');
  const [pin, setPin] = useState('');
  const [requestedBy, setRequestedBy] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const reset = () => {
    setMode('choose');
    setPin('');
    setRequestedBy('');
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const verifyAndPost = async () => {
    if (!pin.trim()) return;
    setVerifying(true);
    setError(null);
    try {
      const res = await fetch(API_ENDPOINTS.DESIGNER_VERIFY_PIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json();
      if (!data.valid) {
        setError('Incorrect PIN. Try again or send the post for approval.');
        return;
      }
      onConfirmDesigner(pin);
    } catch {
      setError('Could not verify PIN. Please try again.');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        {mode === 'choose' && (
          <>
            <h2 className="text-xl font-bold text-slate-900 mb-1">
              Are you the designer?
            </h2>
            <p className="text-sm text-slate-500 mb-5">
              Posts must be approved by the designer before going live. If you are the
              designer, verify with your PIN to post directly. Otherwise, send this post
              for approval.
            </p>
            <div className="space-y-3">
              <button
                onClick={() => {
                  setError(null);
                  setMode('designer');
                }}
                className="w-full py-3 px-4 rounded-lg bg-slate-900 text-white font-medium hover:bg-black transition-colors"
              >
                Yes, I&apos;m the designer
              </button>
              <button
                onClick={() => {
                  setError(null);
                  setMode('requester');
                }}
                className="w-full py-3 px-4 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors"
              >
                No, send for approval
              </button>
              <button
                onClick={close}
                className="w-full py-2.5 px-4 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </>
        )}

        {mode === 'designer' && (
          <>
            <h2 className="text-xl font-bold text-slate-900 mb-1">Designer verification</h2>
            <p className="text-sm text-slate-500 mb-4">
              Enter the designer PIN to publish this post directly.
            </p>
            <input
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="Designer PIN"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') verifyAndPost();
              }}
              className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
            />
            {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={verifyAndPost}
                disabled={verifying || submitting || !pin.trim()}
                className="flex-1 py-2.5 px-4 rounded-lg bg-green-600 text-white font-medium hover:bg-green-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                {verifying ? 'Verifying...' : submitting ? 'Posting...' : 'Verify & Post'}
              </button>
              <button
                onClick={() => {
                  setError(null);
                  setMode('choose');
                }}
                className="px-4 py-2.5 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
              >
                Back
              </button>
            </div>
          </>
        )}

        {mode === 'requester' && (
          <>
            <h2 className="text-xl font-bold text-slate-900 mb-1">Send for approval</h2>
            <p className="text-sm text-slate-500 mb-4">
              The designer will review this post
              {emailConfigured ? ' by email' : ' in the QA Checker'} and approve or reject it.
              It will only be published after approval.
            </p>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Your name (optional)
            </label>
            <input
              type="text"
              value={requestedBy}
              onChange={(e) => setRequestedBy(e.target.value)}
              placeholder="e.g., Sara from marketing"
              autoFocus
              className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
            />
            <div className="flex gap-2">
              <button
                onClick={() => onSubmitApproval(requestedBy.trim())}
                disabled={submitting}
                className="flex-1 py-2.5 px-4 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? 'Submitting...' : 'Submit for approval'}
              </button>
              <button
                onClick={() => setMode('choose')}
                className="px-4 py-2.5 rounded-lg bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
              >
                Back
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
