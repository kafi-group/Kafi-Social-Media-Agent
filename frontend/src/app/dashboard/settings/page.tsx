'use client';

import { useEffect, useState } from 'react';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useTheme } from '@/contexts/ThemeContext';
import { API_ENDPOINTS, fetchWithTimeout } from '@/lib/api-client';
import { LinkedInAccountInfo } from '@/lib/types';

interface ConnectedAccount {
  id?: string;
  name?: string;
  username?: string;
  custom_url?: string;
  configured_id?: string;
  id_matches?: boolean | null;
  error?: string;
}

interface PlatformConfig {
  platforms: Record<string, boolean>;
  draft_mode: boolean;
  connected_accounts?: {
    facebook?: ConnectedAccount | null;
    instagram?: ConnectedAccount | null;
    youtube?: ConnectedAccount | null;
  };
  linkedin_accounts: LinkedInAccountInfo[];
  linkedin_account_count: number;
}

export default function SettingsPage() {
  const { theme } = useTheme();
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWithTimeout(API_ENDPOINTS.PLATFORM_CONFIG)
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load platform config');
        return res.json() as Promise<PlatformConfig>;
      })
      .then(setConfig)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load settings'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Settings</h1>

      <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800 dark:border dark:border-slate-700">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">Appearance</h2>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
          Choose light mode or night mode. Your preference is saved on this device.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-600 dark:bg-slate-900/60">
          <div>
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">Theme</p>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Currently using {theme === 'dark' ? 'Night' : 'Light'} mode
            </p>
          </div>
          <ThemeToggle variant="segmented" />
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6 dark:bg-slate-800 dark:border dark:border-slate-700">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Connected Platforms</h2>

        {loading && <p className="text-gray-500 text-sm">Loading configuration...</p>}
        {error && (
          <p className="text-red-600 text-sm">
            {error}. Make sure the backend is running on port 8000.
          </p>
        )}

        {config && (
          <div className="space-y-4">
            <div
              className={`rounded-lg border px-4 py-3 text-sm ${
                config.draft_mode
                  ? 'border-amber-200 bg-amber-50 text-amber-900'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-900'
              }`}
            >
              <p className="font-semibold">
                {config.draft_mode ? 'Draft mode is ON' : 'Live posting is ON'}
              </p>
              <p className="text-xs mt-1 opacity-80">
                {config.draft_mode
                  ? 'Posts are simulated until DRAFT_MODE=False in backend .env.'
                  : 'Posts go to your connected Facebook, Instagram, and YouTube accounts.'}
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(config.platforms).map(([platform, ready]) => (
                <div
                  key={platform}
                  className={`p-3 rounded-lg border text-center ${
                    ready ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <p className="text-sm font-medium capitalize text-gray-800">{platform}</p>
                  <p className={`text-xs mt-1 font-semibold ${ready ? 'text-green-700' : 'text-gray-500'}`}>
                    {ready ? 'Configured' : 'Not configured'}
                  </p>
                </div>
              ))}
            </div>

            {config.connected_accounts && (
              <div className="border-t pt-4 space-y-3">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Live posting targets
                </h3>
                {(['facebook', 'instagram', 'youtube'] as const).map((platform) => {
                  const account = config.connected_accounts?.[platform];
                  const ready = config.platforms[platform];
                  return (
                    <div
                      key={platform}
                      className="flex items-start justify-between gap-3 text-sm rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-600 dark:bg-slate-900/60"
                    >
                      <div>
                        <p className="font-medium capitalize text-slate-900 dark:text-slate-100">
                          {platform}
                        </p>
                        {account?.error ? (
                          <p className="text-xs text-red-600 mt-1">{account.error}</p>
                        ) : account?.name || account?.username ? (
                          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                            {platform === 'instagram' && account.username
                              ? `@${account.username}`
                              : account.name}
                            {account.custom_url ? ` · ${account.custom_url}` : ''}
                          </p>
                        ) : (
                          <p className="text-xs text-slate-500 mt-1">
                            {ready ? 'Configured (name lookup pending)' : 'Not configured'}
                          </p>
                        )}
                        {account?.id_matches === false && (
                          <p className="text-xs text-amber-700 mt-1">
                            .env ID does not match OAuth account — re-authorize and update .env
                          </p>
                        )}
                      </div>
                      <span
                        className={`text-xs font-semibold shrink-0 ${
                          ready ? 'text-green-700' : 'text-gray-500'
                        }`}
                      >
                        {ready ? 'Ready' : 'Missing'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">
                LinkedIn Accounts ({config.linkedin_account_count})
              </h3>
              {config.linkedin_accounts.length === 0 ? (
                <p className="text-sm text-gray-500">
                  No LinkedIn accounts configured. Add credentials in backend <code>.env</code>.
                </p>
              ) : (
                <ul className="space-y-2">
                  {config.linkedin_accounts.map((account) => (
                    <li
                      key={account.label}
                      className="flex items-center justify-between text-sm bg-blue-50 border border-blue-100 rounded-lg px-4 py-2"
                    >
                      <span className="font-medium text-gray-800">{account.label}</span>
                      <span className="text-xs text-green-700 font-semibold">Account {account.index} · Ready</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-gray-500 mt-3">
                Credentials are stored in backend <code>.env</code> (access token + person ID per account).
                Use the Content Generator to pick which accounts to post from.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
