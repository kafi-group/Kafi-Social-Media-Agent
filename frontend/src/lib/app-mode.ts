/**
 * Access control for the dashboard.
 *
 * Layers:
 * 1. Deployment — NEXT_PUBLIC_APP_MODE=creation-only (env override, Prompt Studio only)
 * 2. User tier — from login JWT/cookie: senior (full) | junior (creation + posting)
 */

export type AccessTier = 'senior' | 'junior';
export type EffectiveMode = 'full' | 'creation-only' | 'junior';

export const TIER_COOKIE = 'dashboard_tier';
export const TIER_PREF_KEY = 'dashboard_tier_preference';

const CREATION_HOME = '/dashboard/creation';
const POSTING_HOME = '/dashboard/generator';

/** Paths a junior developer may access (creation + content posting). */
export const JUNIOR_ALLOWED_PATHS = [CREATION_HOME, POSTING_HOME] as const;

export function isDeploymentCreationOnly(): boolean {
  return process.env.NEXT_PUBLIC_APP_MODE === 'creation-only';
}

export function parseAccessTier(value: string | null | undefined): AccessTier | null {
  if (value === 'junior' || value === 'senior') {
    return value;
  }
  return null;
}

/** Read tier from document.cookie (client only). */
export function getAccessTierFromCookie(): AccessTier | null {
  if (typeof document === 'undefined') {
    return null;
  }
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${TIER_COOKIE}=(junior|senior)(?:;|$)`),
  );
  return parseAccessTier(match?.[1]);
}

export function isJuniorTier(tier?: AccessTier | null): boolean {
  const resolved = tier ?? getAccessTierFromCookie();
  return resolved === 'junior';
}

export function getEffectiveMode(tier?: AccessTier | null): EffectiveMode {
  if (isDeploymentCreationOnly()) {
    return 'creation-only';
  }
  if (isJuniorTier(tier)) {
    return 'junior';
  }
  return 'full';
}

/** True when only Prompt Studio is available (deployment env, not junior workspace). */
export function isCreationOnlyMode(tier?: AccessTier | null): boolean {
  return getEffectiveMode(tier) === 'creation-only';
}

export function getDefaultDashboardPath(tier?: AccessTier | null): string {
  const mode = getEffectiveMode(tier);
  if (mode === 'creation-only' || mode === 'junior') {
    return CREATION_HOME;
  }
  return '/dashboard';
}

/** @deprecated use getDefaultDashboardPath */
export const DEFAULT_DASHBOARD_PATH = getDefaultDashboardPath();

export interface NavItem {
  href: string;
  label: string;
  locked: boolean;
}

const FULL_NAV_ITEMS: Omit<NavItem, 'locked'>[] = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/dashboard/creation', label: 'Content Creation' },
  { href: '/dashboard/generator', label: 'Content Posting' },
  { href: '/dashboard/calendar', label: 'Calendar' },
  { href: '/dashboard/analytics', label: 'Analytics' },
  { href: '/dashboard/qa', label: 'QA Checker' },
  { href: '/dashboard/rivals', label: 'Rival Review' },
];

function isJuniorAllowedPath(pathname: string): boolean {
  return JUNIOR_ALLOWED_PATHS.some(
    (allowed) => pathname === allowed || pathname.startsWith(`${allowed}/`),
  );
}

export function getNavItems(tier?: AccessTier | null): NavItem[] {
  const mode = getEffectiveMode(tier);

  return FULL_NAV_ITEMS.map((item) => {
    if (mode === 'full') {
      return { ...item, locked: false };
    }
    if (mode === 'creation-only') {
      return { ...item, locked: item.href !== CREATION_HOME };
    }
    // junior workspace
    return {
      ...item,
      locked: !JUNIOR_ALLOWED_PATHS.includes(
        item.href as (typeof JUNIOR_ALLOWED_PATHS)[number],
      ),
    };
  });
}

export function isDashboardPathAllowed(
  pathname: string,
  tier?: AccessTier | null,
): boolean {
  const mode = getEffectiveMode(tier);

  if (mode === 'full') {
    return true;
  }

  if (pathname === '/dashboard') {
    return false;
  }

  if (mode === 'creation-only') {
    return pathname === CREATION_HOME || pathname.startsWith(`${CREATION_HOME}/`);
  }

  return isJuniorAllowedPath(pathname);
}

export function getAppDisplayName(tier?: AccessTier | null): string {
  const mode = getEffectiveMode(tier);
  if (mode === 'creation-only' || mode === 'junior') {
    return 'Kafi Prompt Studio';
  }
  return process.env.NEXT_PUBLIC_APP_NAME || 'Kafi Social Agent';
}

export function getAppSubtitle(tier?: AccessTier | null): string {
  const mode = getEffectiveMode(tier);
  if (mode === 'junior') {
    return 'Junior — Creation & Posting';
  }
  if (mode === 'creation-only') {
    return 'Creative prompt studio for images, voice, and Meta AI visuals';
  }
  return 'Social Media Agent';
}

export function getTierLabel(tier: AccessTier): string {
  return tier === 'junior' ? 'Junior Developer' : 'Senior Developer';
}
