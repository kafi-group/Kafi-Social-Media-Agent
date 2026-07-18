'use client';

import React, { FormEvent, useEffect, useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { API_ENDPOINTS } from '@/lib/api-client';
import { clearSession, setSession } from '@/lib/auth';
import {
  getDefaultDashboardPath,
  isDashboardPathAllowed,
  parseAccessTier,
} from '@/lib/app-mode';

export default function LoginPage() {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Drop any leftover forgeable session cookies before showing the form.
  useEffect(() => {
    clearSession();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(API_ENDPOINTS.AUTH_LOGIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : 'Login failed. Check your username and password.',
        );
        return;
      }

      if (typeof data.access_token !== 'string' || !data.access_token.includes('.')) {
        setError('Login response was missing a valid access token.');
        return;
      }

      const role = parseAccessTier(data.role) ?? 'senior';
      setSession(data.access_token, data.expires_in ?? 28800, role);

      const params = new URLSearchParams(window.location.search);
      const from = params.get('from');
      const defaultPath = getDefaultDashboardPath(role);

      if (from && from.startsWith('/dashboard') && isDashboardPathAllowed(from, role)) {
        router.replace(from);
      } else {
        router.replace(defaultPath);
      }
    } catch {
      setError('Could not reach the server. Try again in a moment.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-gold-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <div className="mb-6 flex justify-center">
          <Image
            src="/kafi-logo.png"
            alt="Kafi Commodities"
            width={200}
            height={64}
            className="object-contain"
            priority
          />
        </div>

        <h1 className="mb-1 text-center text-2xl font-bold text-slate-900">
          Dashboard Login
        </h1>
        <p className="mb-6 text-center text-sm text-slate-600">
          Sign in with your senior or junior developer account.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="username"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 pr-11 text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" aria-hidden />
                ) : (
                  <Eye className="h-5 w-5" aria-hidden />
                )}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-700 py-2.5 font-semibold text-white transition hover:bg-brand-800 disabled:opacity-60"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-500">
          Junior accounts can use Content Creation and Content Posting; posts go to the
          QA Checker for senior approval.
        </p>
      </div>
    </main>
  );
}
