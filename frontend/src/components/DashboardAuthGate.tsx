'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { API_ENDPOINTS } from '@/lib/api-client';
import { clearSession, getAuthToken, isLegacySessionCookie } from '@/lib/auth';
import {
  type AccessTier,
  parseAccessTier,
  TIER_COOKIE,
  TIER_PREF_KEY,
} from '@/lib/app-mode';

/**
 * Client-side gate: even if middleware were bypassed, pages still require a
 * live JWT that the backend accepts via /auth/me.
 */
export default function DashboardAuthGate({
  children,
  onAuthenticated,
}: {
  children: ReactNode;
  onAuthenticated?: (tier: AccessTier) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      const token = getAuthToken();
      if (!token || isLegacySessionCookie(token)) {
        clearSession();
        router.replace(`/login?from=${encodeURIComponent(pathname || '/dashboard')}`);
        return;
      }

      try {
        const res = await fetch(API_ENDPOINTS.AUTH_ME, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
          cache: 'no-store',
        });

        if (!res.ok) {
          clearSession();
          router.replace(`/login?from=${encodeURIComponent(pathname || '/dashboard')}`);
          return;
        }

        const data = (await res.json().catch(() => ({}))) as { role?: string };
        const tier = parseAccessTier(data.role) ?? 'senior';
        if (typeof window !== 'undefined') {
          localStorage.setItem(TIER_PREF_KEY, tier);
          const secure = window.location.protocol === 'https:' ? '; Secure' : '';
          document.cookie = `${TIER_COOKIE}=${tier}; path=/; max-age=28800; SameSite=Lax${secure}`;
        }
        if (!cancelled) {
          onAuthenticated?.(tier);
          setReady(true);
        }
      } catch {
        clearSession();
        router.replace(`/login?from=${encodeURIComponent(pathname || '/dashboard')}`);
      }
    }

    void verify();
    return () => {
      cancelled = true;
    };
  }, [pathname, router, onAuthenticated]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <p className="text-sm text-slate-600 dark:text-slate-300">Checking session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
