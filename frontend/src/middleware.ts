import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const CREATION_HOME = '/dashboard/creation';
const SESSION_COOKIE = 'dashboard_session';
const TIER_COOKIE = 'dashboard_tier';

const JUNIOR_ALLOWED_PREFIXES = ['/dashboard/creation', '/dashboard/generator'];

function isCreationOnlyDashboardPath(pathname: string): boolean {
  return pathname === CREATION_HOME || pathname.startsWith(`${CREATION_HOME}/`);
}

function isJuniorDashboardPath(pathname: string): boolean {
  return JUNIOR_ALLOWED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

function resolveApiBaseUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').trim();
  if (raw.startsWith('NEXT_PUBLIC_API_URL=')) {
    return raw.slice('NEXT_PUBLIC_API_URL='.length).trim().replace(/\/$/, '');
  }
  return raw.replace(/\/$/, '');
}

/** Reject empty / legacy forgeable cookie values like "1". */
function isUsableSessionToken(value: string | undefined): value is string {
  if (!value) return false;
  const v = value.trim();
  if (!v || v === '1' || v === 'true' || v === 'yes') return false;
  // JWTs are three base64url segments separated by dots.
  return v.split('.').length === 3;
}

function redirectToLogin(request: NextRequest): NextResponse {
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('from', request.nextUrl.pathname);
  const response = NextResponse.redirect(loginUrl);
  // Drop forgeable / invalid session cookies so the bypass cannot stick.
  response.cookies.set(SESSION_COOKIE, '', { path: '/', maxAge: 0 });
  response.cookies.set(TIER_COOKIE, '', { path: '/', maxAge: 0 });
  return response;
}

async function verifySessionWithBackend(
  token: string,
): Promise<{ ok: true; role: string } | { ok: false }> {
  const apiBase = resolveApiBaseUrl();
  try {
    const res = await fetch(`${apiBase}/api/v1/auth/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
      cache: 'no-store',
    });
    if (!res.ok) {
      return { ok: false };
    }
    const data = (await res.json().catch(() => null)) as { role?: string } | null;
    const role = data?.role === 'junior' ? 'junior' : 'senior';
    return { ok: true, role };
  } catch {
    // Fail closed: if we cannot verify the session, deny dashboard access.
    return { ok: false };
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const rawSession = request.cookies.get(SESSION_COOKIE)?.value;
  const token = rawSession ? decodeURIComponent(rawSession) : undefined;

  if (!isUsableSessionToken(token)) {
    return redirectToLogin(request);
  }

  const verified = await verifySessionWithBackend(token);
  if (!verified.ok) {
    return redirectToLogin(request);
  }

  // Prefer the verified JWT role over a client-writable tier cookie.
  const role = verified.role;

  if (process.env.NEXT_PUBLIC_APP_MODE === 'creation-only' && pathname.startsWith('/dashboard')) {
    if (pathname === '/dashboard' || !isCreationOnlyDashboardPath(pathname)) {
      return NextResponse.redirect(new URL(CREATION_HOME, request.url));
    }
  } else if (role === 'junior' && pathname.startsWith('/dashboard')) {
    if (pathname === '/dashboard' || !isJuniorDashboardPath(pathname)) {
      return NextResponse.redirect(new URL(CREATION_HOME, request.url));
    }
  }

  const response = NextResponse.next();
  // Keep the tier cookie aligned with the verified role for client UI.
  response.cookies.set(TIER_COOKIE, role, {
    path: '/',
    sameSite: 'lax',
    secure: request.nextUrl.protocol === 'https:',
  });
  return response;
}

export const config = {
  matcher: ['/dashboard', '/dashboard/:path*'],
};
