/**
 * API Client Configuration - Updated for media & social posting
 */

import { getAuthHeaders, clearSession } from './auth';

/** Normalize API base URL (handles Vercel env pasted as `NEXT_PUBLIC_API_URL=https://...`). */
function resolveApiBaseUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').trim();
  if (raw.startsWith('NEXT_PUBLIC_API_URL=')) {
    return raw.slice('NEXT_PUBLIC_API_URL='.length).trim();
  }
  return raw;
}

const API_BASE_URL = resolveApiBaseUrl();
const API_VERSION = 'v1';

export const API_ENDPOINTS = {
  // Auth
  AUTH_LOGIN: `${API_BASE_URL}/api/${API_VERSION}/auth/login`,
  AUTH_ME: `${API_BASE_URL}/api/${API_VERSION}/auth/me`,

  // Health
  HEALTH: `${API_BASE_URL}/api/${API_VERSION}/health`,

  // Content
  CONTENT_GENERATE: `${API_BASE_URL}/api/${API_VERSION}/content/generate`,
  CONTENT_GENERATE_WITH_MEDIA: `${API_BASE_URL}/api/${API_VERSION}/content/generate-with-media`,
  CONTENT_HISTORY: `${API_BASE_URL}/api/${API_VERSION}/content/history`,
  CONTENT_DETAIL: (id: number) => `${API_BASE_URL}/api/${API_VERSION}/content/${id}`,
  CONTENT_REGENERATE: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/content/${id}/regenerate`,

  // Media
  MEDIA_UPLOAD: `${API_BASE_URL}/api/${API_VERSION}/content/media/upload`,

  // Social Posting
  SOCIAL_POST: (id: number) => `${API_BASE_URL}/api/${API_VERSION}/content/${id}/post`,
  LINKEDIN_ACCOUNTS: `${API_BASE_URL}/api/${API_VERSION}/social/linkedin/accounts`,
  PLATFORM_CONFIG: `${API_BASE_URL}/api/${API_VERSION}/social/platforms/config`,

  // Calendar / Scheduling
  CALENDAR_EVENTS: `${API_BASE_URL}/api/${API_VERSION}/calendar/events`,
  CALENDAR_EVENT: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/calendar/events/${id}`,
  CALENDAR_PUBLISH_NOW: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/calendar/events/${id}/publish-now`,

  // Analytics
  ANALYTICS_OVERVIEW: `${API_BASE_URL}/api/${API_VERSION}/analytics/overview`,
  ANALYTICS_SUMMARY: (range: string = '30d') =>
    `${API_BASE_URL}/api/${API_VERSION}/analytics/summary?range=${range}`,
  ANALYTICS_PLATFORM: (platform: string, range: string = '30d') =>
    `${API_BASE_URL}/api/${API_VERSION}/analytics/${platform}?range=${range}`,
  ANALYTICS_TRENDS: `${API_BASE_URL}/api/${API_VERSION}/analytics/trends`,

  // Content Creation (chatbot)
  CREATION_MODELS: `${API_BASE_URL}/api/${API_VERSION}/creation/models`,
  CREATION_CHAT: `${API_BASE_URL}/api/${API_VERSION}/creation/chat`,
  CREATION_GENERATE_IMAGE: `${API_BASE_URL}/api/${API_VERSION}/creation/generate-image`,
  CREATION_GENERATE_VOICE: `${API_BASE_URL}/api/${API_VERSION}/creation/generate-voice`,

  // QA
  QA_CHECK: `${API_BASE_URL}/api/${API_VERSION}/qa/check`,

  // Content management
  CONTENT_CLEAR_ALL: `${API_BASE_URL}/api/${API_VERSION}/content/clear-all`,
  CONTENT_CLEAR_STATS: `${API_BASE_URL}/api/${API_VERSION}/content/clear-stats`,

  // Designer Approval Workflow
  APPROVAL_STATS: `${API_BASE_URL}/api/${API_VERSION}/approvals/stats`,
  APPROVAL_CONFIG: `${API_BASE_URL}/api/${API_VERSION}/approvals/config`,
  DESIGNER_VERIFY_PIN: `${API_BASE_URL}/api/${API_VERSION}/designer/verify-pin`,
  APPROVALS: `${API_BASE_URL}/api/${API_VERSION}/approvals`,
  APPROVAL_DETAIL: (id: number) => `${API_BASE_URL}/api/${API_VERSION}/approvals/${id}`,
  APPROVAL_APPROVE: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/approvals/${id}/approve`,
  APPROVAL_REJECT: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/approvals/${id}/reject`,

  // Rival Review (competitor intelligence)
  RIVALS: `${API_BASE_URL}/api/${API_VERSION}/rivals`,
  RIVAL_DETAIL: (id: number) => `${API_BASE_URL}/api/${API_VERSION}/rivals/${id}`,
  RIVAL_REFRESH: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/rivals/${id}/refresh`,
  RIVALS_REFRESH_ALL: `${API_BASE_URL}/api/${API_VERSION}/rivals/refresh-all`,
  RIVAL_SNAPSHOTS: (id: number) =>
    `${API_BASE_URL}/api/${API_VERSION}/rivals/${id}/snapshots`,
  RIVALS_INSIGHTS: `${API_BASE_URL}/api/${API_VERSION}/rivals/insights`,
  RIVALS_CONFIG: `${API_BASE_URL}/api/${API_VERSION}/rivals/config`,

  // Uploads
  UPLOADS: `${API_BASE_URL}/uploads`,
};

export const API_CONFIG = {
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 min timeout for generation
  readTimeout: 10000, // 10s for dashboard/list reads — fail fast instead of hanging
  headers: {
    'Content-Type': 'application/json',
  },
};

/** Merge default JSON + auth headers into a fetch init object. */
function withAuthHeaders(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  for (const [key, value] of Object.entries(getAuthHeaders())) {
    headers.set(key, value);
  }
  return { ...init, headers };
}

/** Authenticated fetch — use for all API calls after login. */
export async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, withAuthHeaders(init));
  if (response.status === 401 && typeof window !== 'undefined') {
    clearSession();
    window.location.href = '/login';
  }
  return response;
}

/** Fetch with an abort timeout so slow/unreachable backends don't freeze the UI. */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const { timeoutMs = API_CONFIG.readTimeout, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(new DOMException(`Request timed out after ${timeoutMs / 1000}s`, 'TimeoutError')),
    timeoutMs,
  );
  try {
    return await apiFetch(input, { ...fetchInit, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && (err.name === 'AbortError' || err.name === 'TimeoutError')) {
      throw new Error(
        err.name === 'TimeoutError' || err.message.includes('timed out')
          ? `Request timed out after ${timeoutMs / 1000}s — is the backend running?`
          : 'Request was cancelled',
      );
    }
    // Browsers sometimes surface abort as a plain Error with this message
    if (err instanceof Error && /signal is aborted/i.test(err.message)) {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s — is the backend running?`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
