/**
 * Dashboard session — JWT in localStorage (API calls) + cookie (Next.js middleware).
 *
 * Security: the cookie MUST contain the real JWT. Middleware verifies it with the
 * backend /auth/me endpoint. A forgeable flag like "dashboard_session=1" is rejected.
 */

import type { AccessTier } from '@/lib/app-mode';
import { TIER_COOKIE, TIER_PREF_KEY } from '@/lib/app-mode';

const TOKEN_KEY = 'dashboard_token';
export const SESSION_COOKIE = 'dashboard_session';

function cookieFlags(maxAgeSeconds: number): string {
  const secure =
    typeof window !== 'undefined' && window.location.protocol === 'https:'
      ? '; Secure'
      : '';
  return `; path=/; max-age=${maxAgeSeconds}; SameSite=Lax${secure}`;
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=([^;]*)`),
  );
  if (!match?.[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

/** True when the cookie is the legacy forgeable placeholder (not a JWT). */
export function isLegacySessionCookie(value: string | null | undefined): boolean {
  if (!value) return false;
  const v = value.trim();
  return v === '1' || v === 'true' || v === 'yes';
}

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  const fromStorage = localStorage.getItem(TOKEN_KEY);
  if (fromStorage && !isLegacySessionCookie(fromStorage)) {
    return fromStorage;
  }
  const fromCookie = readCookie(SESSION_COOKIE);
  if (fromCookie && !isLegacySessionCookie(fromCookie)) {
    return fromCookie;
  }
  return null;
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export function setSession(
  token: string,
  expiresInSeconds: number,
  tier: AccessTier = 'senior',
): void {
  if (!token || isLegacySessionCookie(token)) {
    throw new Error('Refusing to store an invalid dashboard session token.');
  }

  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TIER_PREF_KEY, tier);

  const flags = cookieFlags(expiresInSeconds);
  // Store the JWT itself — middleware verifies it server-side.
  document.cookie = `${SESSION_COOKIE}=${encodeURIComponent(token)}${flags}`;
  document.cookie = `${TIER_COOKIE}=${tier}${flags}`;
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0`;
  document.cookie = `${TIER_COOKIE}=; path=/; max-age=0`;
}

export function isLoggedIn(): boolean {
  return Boolean(getAuthToken());
}

export function logout(): void {
  clearSession();
  window.location.href = '/login';
}
