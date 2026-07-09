'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertCircle,
  BarChart3,
  Eye,
  MessageCircle,
  Share2,
  ThumbsUp,
  Users,
} from 'lucide-react';

import { API_ENDPOINTS, fetchWithTimeout } from '@/lib/api-client';
import type {
  AnalyticsPlatform,
  AnalyticsSummaryResponse,
  PlatformAnalyticsResponse,
} from '@/lib/types';

const platforms: Array<{
  id: AnalyticsPlatform;
  label: string;
  accent: string;
}> = [
  { id: 'facebook', label: 'Facebook', accent: 'bg-blue-500' },
  { id: 'instagram', label: 'Instagram', accent: 'bg-pink-500' },
  { id: 'youtube', label: 'YouTube', accent: 'bg-red-600' },
  { id: 'tiktok', label: 'TikTok', accent: 'bg-gray-900' },
];

const ranges = [
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
  { label: '90 days', value: '90d' },
];

const emptyPlatform = (platform: AnalyticsPlatform): PlatformAnalyticsResponse => ({
  platform,
  status: 'not_configured',
  range: { start: '', end: '', days: 30 },
  totals: {},
  series: [],
  message: 'Analytics data has not loaded yet.',
});

const formatNumber = (value?: number) => {
  if (!value) return '0';
  return new Intl.NumberFormat('en-US', {
    notation: value >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value);
};

const statusLabel = (status: PlatformAnalyticsResponse['status']) => {
  switch (status) {
    case 'ok':
      return 'Connected';
    case 'not_configured':
      return 'Not configured';
    case 'permission_error':
      return 'Permission needed';
    default:
      return 'API error';
  }
};

export default function AnalyticsPage() {
  const [range, setRange] = useState('30d');
  const [activePlatform, setActivePlatform] = useState<AnalyticsPlatform>('facebook');
  const [summary, setSummary] = useState<AnalyticsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadAnalytics() {
      try {
        setIsLoading(true);
        setError(null);

        const response = await fetchWithTimeout(API_ENDPOINTS.ANALYTICS_SUMMARY(range), {
          signal: controller.signal,
          timeoutMs: 15000,
        });

        if (!response.ok) {
          throw new Error(`Analytics request failed (${response.status})`);
        }

        const data = (await response.json()) as AnalyticsSummaryResponse;
        setSummary(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load analytics');
      } finally {
        setIsLoading(false);
      }
    }

    loadAnalytics();

    return () => controller.abort();
  }, [range]);

  const activeData = useMemo(() => {
    return (
      summary?.platforms.find((platform) => platform.platform === activePlatform) ??
      emptyPlatform(activePlatform)
    );
  }, [activePlatform, summary]);

  const visiblePlatforms = useMemo(() => {
    return platforms.map((platform) => ({
      ...platform,
      data:
        summary?.platforms.find((item) => item.platform === platform.id) ??
        emptyPlatform(platform.id),
    }));
  }, [summary]);

  const totals = activeData.totals;
  const primaryViews = totals.views ?? totals.reach ?? totals.impressions ?? 0;
  const audience = totals.followers ?? totals.subscribers ?? 0;

  return (
    <div className="max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Analytics</h1>
          <p className="mt-1 text-gray-600">
            Real account-level reach and engagement across your social platforms.
          </p>
        </div>

        <div className="flex rounded-lg border border-gray-200 bg-white p-1 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          {ranges.map((option) => (
            <button
              key={option.value}
              onClick={() => setRange(option.value)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                range === option.value
                  ? 'bg-gray-900 text-white dark:bg-slate-600'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {visiblePlatforms.map(({ id, label, accent, data }) => (
          <button
            key={id}
            onClick={() => setActivePlatform(id)}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm transition hover:shadow-md dark:bg-slate-800 dark:border-slate-600 ${
              activePlatform === id ? 'border-gray-900 dark:border-gold-500' : 'border-gray-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className={`h-2.5 w-2.5 rounded-full ${accent}`} />
              <span
                className={`rounded-full px-2 py-1 text-xs font-medium ${
                  data.status === 'ok'
                    ? 'bg-green-100 text-green-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                    : 'bg-gold-50 text-gold-700 border border-gold-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60'
                }`}
              >
                {statusLabel(data.status)}
              </span>
            </div>
            <h2 className="mt-4 text-lg font-semibold text-gray-900">{label}</h2>
            <p className="mt-2 text-sm text-gray-500">
              {data.message || 'No status message available.'}
            </p>
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={<Eye className="h-5 w-5" />}
          label="Views / Reach"
          value={formatNumber(primaryViews)}
        />
        <MetricCard
          icon={<BarChart3 className="h-5 w-5" />}
          label="Engagements"
          value={formatNumber(totals.engagements)}
        />
        <MetricCard
          icon={<Users className="h-5 w-5" />}
          label={activePlatform === 'youtube' ? 'Subscribers gained' : 'Followers'}
          value={formatNumber(audience)}
        />
        <MetricCard
          icon={<MessageCircle className="h-5 w-5" />}
          label="Comments"
          value={formatNumber(totals.comments)}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm xl:col-span-2 dark:border-slate-600 dark:bg-slate-800">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {platforms.find((platform) => platform.id === activePlatform)?.label} trend
              </h2>
              <p className="text-sm text-gray-500">
                {activeData.range.start && activeData.range.end
                  ? `${activeData.range.start} to ${activeData.range.end}`
                  : 'Select a platform to view trend data.'}
              </p>
            </div>
            {isLoading && <span className="text-sm text-gray-500">Loading...</span>}
          </div>

          {activeData.status !== 'ok' ? (
            <EmptyState message={activeData.message || 'Analytics is not available.'} />
          ) : activeData.series.length === 0 ? (
            <EmptyState message="No trend rows were returned for this date range." />
          ) : (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activeData.series}>
                  <defs>
                    <linearGradient id="views" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="views"
                    name="Views / reach"
                    stroke="#2563eb"
                    fill="url(#views)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="engagements"
                    name="Engagements"
                    stroke="#16a34a"
                    fill="transparent"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100">Breakdown</h2>
          <div className="mt-5 space-y-4">
            <BreakdownRow label="Impressions" value={totals.impressions} />
            <BreakdownRow label="Reach" value={totals.reach} />
            <BreakdownRow label="Likes" value={totals.likes} icon={<ThumbsUp />} />
            <BreakdownRow label="Comments" value={totals.comments} icon={<MessageCircle />} />
            <BreakdownRow label="Shares" value={totals.shares} icon={<Share2 />} />
            <BreakdownRow label="Watch time (min)" value={totals.watch_time_minutes} />
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-slate-200">
        {icon}
      </div>
      <p className="text-sm font-medium text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-slate-100">{value}</p>
    </div>
  );
}

function BreakdownRow({
  label,
  value,
  icon,
}: {
  label: string;
  value?: number;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3 dark:bg-slate-900/60">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-slate-400">
        {icon && <span className="h-4 w-4 text-gray-400">{icon}</span>}
        {label}
      </div>
      <span className="font-semibold text-gray-900 dark:text-slate-100">{formatNumber(value)}</span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-80 items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
      <div>
        <AlertCircle className="mx-auto h-8 w-8 text-gold-500" />
        <p className="mt-3 max-w-md text-sm text-gray-600">{message}</p>
      </div>
    </div>
  );
}
