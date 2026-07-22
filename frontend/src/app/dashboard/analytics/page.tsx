'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  BarChart3,
  Bookmark,
  Check,
  Clock,
  Eye,
  MessageCircle,
  Play,
  Radio,
  Repeat2,
  Send,
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
  { id: 'linkedin', label: 'LinkedIn', accent: 'bg-[#0A66C2]' },
];

const ranges = [
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
  { label: '90 days', value: '90d' },
];

/** Configured LinkedIn analytics (fixed snapshot from channel data). */
const LINKEDIN_STATIC = {
  impressions: 1516,
  impressionsChange: 999,
  followers: 4794,
  followersChange: 1,
  profileViewers: 207,
  profileViewersChange: 1900,
  searchAppearances: 4,
  searchAppearancesChange: 0,
  searchWindow: 'Jul 7–13',
  searchCompareWindow: 'Jun 30–Jul 6',
  membersReached: 664,
  inNetworkPct: 57,
  outOfNetworkPct: 43,
  socialEngagements: 34,
  reactions: 30,
  comments: 2,
  reposts: 0,
  saves: 1,
  sends: 1,
  impressionsSeries: [
    { date: 'Jul 11', value: 12 },
    { date: 'Jul 12', value: 18 },
    { date: 'Jul 13', value: 45 },
    { date: 'Jul 14', value: 820 },
    { date: 'Jul 15', value: 1380 },
    { date: 'Jul 16', value: 1470 },
    { date: 'Jul 17', value: 1516 },
  ],
  followerGrowthSeries: [
    { date: 'Jul 11', value: 1 },
    { date: 'Jul 12', value: 2 },
    { date: 'Jul 13', value: 4 },
    { date: 'Jul 14', value: 18 },
    { date: 'Jul 15', value: 30 },
    { date: 'Jul 16', value: 31 },
    { date: 'Jul 17', value: 32 },
  ],
};

/** Configured YouTube analytics (fixed snapshot from channel data). */
const YOUTUBE_STATIC = {
  dateRange: '18 Jun – 15 Jul 2026',
  channelViews: 679,
  channelViewsDelta: -121,
  watchTimeHours: 1.4,
  channelViewsSeries: [
    { date: '18 Jun', value: 8, upload: false },
    { date: '20 Jun', value: 28, upload: false },
    { date: '23 Jun', value: 42, upload: true },
    { date: '25 Jun', value: 18, upload: false },
    { date: '27 Jun', value: 35, upload: true },
    { date: '29 Jun', value: 22, upload: false },
    { date: '2 Jul', value: 48, upload: true },
    { date: '4 Jul', value: 30, upload: false },
    { date: '6 Jul', value: 55, upload: true },
    { date: '8 Jul', value: 38, upload: false },
    { date: '10 Jul', value: 52, upload: false },
    { date: '12 Jul', value: 44, upload: false },
    { date: '15 Jul', value: 36, upload: false },
  ],
  realtimeSubscribers: 803,
  realtimeViews48h: 37,
  realtimeViews48hSeries: [
    { hour: '-48h', value: 0 },
    { hour: '-44h', value: 1 },
    { hour: '-40h', value: 0 },
    { hour: '-36h', value: 2 },
    { hour: '-32h', value: 1 },
    { hour: '-28h', value: 3 },
    { hour: '-24h', value: 2 },
    { hour: '-20h', value: 4 },
    { hour: '-16h', value: 3 },
    { hour: '-12h', value: 5 },
    { hour: '-8h', value: 4 },
    { hour: '-4h', value: 6 },
    { hour: 'Now', value: 6 },
  ],
  videos: {
    views: 88,
    viewsStatus: 'same' as const,
    impressions: 3700,
    impressionsChange: -59,
    clickThroughRate: 1.6,
    avgViewDuration: '0:28',
    series: [
      { date: '18 Jun', value: 3, upload: false },
      { date: '22 Jun', value: 12, upload: true },
      { date: '25 Jun', value: 5, upload: false },
      { date: '27 Jun', value: 8, upload: true },
      { date: '2 Jul', value: 11, upload: true },
      { date: '6 Jul', value: 9, upload: true },
      { date: '10 Jul', value: 15, upload: false },
      { date: '13 Jul', value: 7, upload: false },
      { date: '15 Jul', value: 4, upload: false },
    ],
  },
  shorts: {
    views: 589,
    viewsDelta: -41,
    engagedViews: 201,
    engagedViewsChange: -21,
    likes: -1,
    likesChange: -150,
    series: [
      { date: '18 Jun', value: 12, upload: false },
      { date: '22 Jun', value: 28, upload: true },
      { date: '25 Jun', value: 18, upload: false },
      { date: '27 Jun', value: 32, upload: true },
      { date: '2 Jul', value: 24, upload: true },
      { date: '6 Jul', value: 38, upload: true },
      { date: '10 Jul', value: 42, upload: false },
      { date: '13 Jul', value: 22, upload: false },
      { date: '15 Jul', value: 15, upload: false },
    ],
  },
};

/** Configured Instagram analytics (fixed snapshot from Account insights). */
const INSTAGRAM_STATIC = {
  dateRange: 'Last 30 days',
  views: {
    total: 443,
    followersPct: 9.7,
    nonFollowersPct: 90.3,
    accountsReached: 361,
    byContentType: {
      all: [
        { label: 'Reels', pct: 95.1 },
        { label: 'Posts', pct: 4.2 },
        { label: 'Videos', pct: 0.7 },
      ],
      followers: [
        { label: 'Reels', pct: 88.2 },
        { label: 'Posts', pct: 8.5 },
        { label: 'Videos', pct: 3.3 },
      ],
      nonFollowers: [
        { label: 'Reels', pct: 96.8 },
        { label: 'Posts', pct: 2.9 },
        { label: 'Videos', pct: 0.3 },
      ],
    },
  },
  profile: {
    activity: 5,
    visits: 5,
    followers: 607,
    mostActiveTimes: [
      { time: '12a', value: 48 },
      { time: '3a', value: 52 },
      { time: '6a', value: 51 },
      { time: '9a', value: 49 },
      { time: '12p', value: 42 },
      { time: '3p', value: 23 },
      { time: '6p', value: 24 },
      { time: '9p', value: 38 },
    ],
  },
  interactions: {
    total: 3,
    followersPct: 66.7,
    nonFollowersPct: 33.3,
    accountsEngaged: 3,
    byContentType: [{ label: 'Reels', pct: 100 }],
  },
};

/** Configured Facebook analytics (fixed snapshot from Insights). */
const FACEBOOK_STATIC = {
  dateRange: 'Last 28 days: 18 Jun–15 Jul',
  views: 651,
  viewsChange: 44,
  engagement: 5,
  engagementChange: 67,
  netFollows: 5,
  netFollowsChange: 600,
  viewsSeries: [
    { date: '19 Jun', value: 8 },
    { date: '21 Jun', value: 155 },
    { date: '24 Jun', value: 12 },
    { date: '27 Jun', value: 120 },
    { date: '29 Jun', value: 5 },
    { date: '4 Jul', value: 3 },
    { date: '9 Jul', value: 2 },
    { date: '14 Jul', value: 18 },
  ],
  content: {
    all: {
      views: 651,
      viewsChange: 44,
      series: [
        { date: '19 Jun', value: 8 },
        { date: '21 Jun', value: 155 },
        { date: '24 Jun', value: 12 },
        { date: '27 Jun', value: 120 },
        { date: '29 Jun', value: 5 },
        { date: '4 Jul', value: 3 },
        { date: '9 Jul', value: 2 },
        { date: '14 Jul', value: 18 },
      ],
    },
    reels: {
      views: 543,
      viewsChange: 109,
      watchTime: '18 m 54 s',
      watchTimeChange: -27,
      series: [
        { date: '18 Jun', value: 5 },
        { date: '22 Jun', value: 160 },
        { date: '25 Jun', value: 10 },
        { date: '27 Jun', value: 115 },
        { date: '2 Jul', value: 4 },
        { date: '8 Jul', value: 3 },
        { date: '13 Jul', value: 8 },
      ],
    },
    posts: {
      views: 701,
      viewsChange: 74.4,
      series: [
        { date: '18 Jun', value: 6 },
        { date: '22 Jun', value: 165 },
        { date: '23 Jun', value: 12 },
        { date: '27 Jun', value: 130 },
        { date: '28 Jun', value: 8 },
        { date: '3 Jul', value: 4 },
        { date: '8 Jul', value: 3 },
        { date: '13 Jul', value: 10 },
      ],
    },
    stories: {
      views: 0,
      viewsChange: 0,
      series: [
        { date: '18 Jun', value: 0 },
        { date: '23 Jun', value: 0 },
        { date: '28 Jun', value: 0 },
        { date: '3 Jul', value: 0 },
        { date: '8 Jul', value: 0 },
        { date: '13 Jul', value: 0 },
      ],
    },
  },
  engagementOverview: {
    total: 5,
    change: 66.7,
    reactions: 3,
    comments: 0,
    shares: 0,
    series: [
      { date: '18 Jun', value: 0 },
      { date: '22 Jun', value: 1 },
      { date: '23 Jun', value: 0 },
      { date: '26 Jun', value: 1 },
      { date: '27 Jun', value: 1 },
      { date: '29 Jun', value: 1 },
      { date: '3 Jul', value: 0 },
      { date: '8 Jul', value: 0 },
      { date: '13 Jul', value: 0 },
      { date: '15 Jul', value: 1 },
    ],
  },
};

const STATIC_PLATFORMS: AnalyticsPlatform[] = ['linkedin'];

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

const statusLabel = (status: PlatformAnalyticsResponse['status'], isStatic = false) => {
  if (isStatic) return 'Configured';
  switch (status) {
    case 'ok':
      return 'Connected';
    case 'not_configured':
      return 'Not configured';
    case 'permission_error':
      return 'Permission needed';
    case 'token_expired':
      return 'Reconnect needed';
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
    return platforms.map((platform) => {
      // LinkedIn has no live analytics API wired — keep the static snapshot only.
      if (platform.id === 'linkedin') {
        return {
          ...platform,
          data: {
            ...emptyPlatform('linkedin'),
            status: 'ok' as const,
            message: `${formatNumber(LINKEDIN_STATIC.impressions)} impressions, ${formatNumber(LINKEDIN_STATIC.followers)} followers.`,
          },
        };
      }
      return {
        ...platform,
        data:
          summary?.platforms.find((item) => item.platform === platform.id) ??
          emptyPlatform(platform.id),
      };
    });
  }, [summary]);

  const totals = activeData.totals;
  const primaryViews = totals.views ?? totals.reach ?? totals.impressions ?? 0;
  const audience = totals.followers ?? totals.subscribers ?? 0;
  const isStaticPlatform = STATIC_PLATFORMS.includes(activePlatform);
  const isLinkedIn = activePlatform === 'linkedin';
  const metaReconnectUrl = API_ENDPOINTS.META_AUTH;
  const needsReconnect =
    activeData.status === 'token_expired' || activeData.status === 'permission_error';

  return (
    <div className="max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Analytics</h1>
          <p className="mt-1 text-gray-600">
            Real account-level reach and engagement across your social platforms.
          </p>
        </div>

        {!isStaticPlatform && (
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
        )}
      </div>

      {error && !isStaticPlatform && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
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
                {statusLabel(data.status, STATIC_PLATFORMS.includes(id))}
              </span>
            </div>
            <h2 className="mt-4 text-lg font-semibold text-gray-900">{label}</h2>
            <p className="mt-2 text-sm text-gray-500">
              {data.message || 'No status message available.'}
            </p>
          </button>
        ))}
      </div>

      {isLinkedIn ? (
        <LinkedInSection />
      ) : (
        <>
          {(activePlatform === 'facebook' || activePlatform === 'instagram') &&
            needsReconnect && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200">
                Meta analytics need a reconnect.{' '}
                <a
                  href={metaReconnectUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold underline underline-offset-2"
                >
                  Reconnect Facebook / Instagram
                </a>
              </div>
            )}

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
              label="Followers"
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
        </>
      )}
    </div>
  );
}

function InstagramSection() {
  const S = INSTAGRAM_STATIC;
  const [viewsAudience, setViewsAudience] = useState<'all' | 'followers' | 'nonFollowers'>('all');

  const viewsContent =
    viewsAudience === 'all'
      ? S.views.byContentType.all
      : viewsAudience === 'followers'
        ? S.views.byContentType.followers
        : S.views.byContentType.nonFollowers;

  const maxActiveTime = Math.max(...S.profile.mostActiveTimes.map((slot) => slot.value));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Account insights</h2>
          <p className="text-sm text-gray-500">Instagram professional dashboard snapshot.</p>
        </div>
        <p className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 dark:border-slate-600 dark:text-slate-300">
          {S.dateRange}
        </p>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="border-b border-gray-100 px-6 py-4 dark:border-slate-700">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">Views</h3>
        </div>
        <div className="grid divide-y divide-gray-100 dark:divide-slate-700 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
          <div className="space-y-5 p-6">
            <div>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.views.total)}
              </p>
              <p className="text-sm text-gray-500">Views</p>
            </div>
            <dl className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <dt className="text-gray-600 dark:text-slate-400">Followers</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {S.views.followersPct}%
                </dd>
              </div>
              <div className="flex items-center justify-between text-sm">
                <dt className="text-gray-600 dark:text-slate-400">Non-followers</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {S.views.nonFollowersPct}%
                </dd>
              </div>
            </dl>
            <div className="border-t border-gray-100 pt-4 dark:border-slate-700">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 dark:text-slate-400">Accounts reached</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.views.accountsReached)}
                </span>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100">By content type</p>
              <div className="flex flex-wrap gap-1.5">
                {(
                  [
                    { id: 'all' as const, label: 'All' },
                    { id: 'followers' as const, label: 'Followers' },
                    { id: 'nonFollowers' as const, label: 'Non-followers' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setViewsAudience(tab.id)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      viewsAudience === tab.id
                        ? 'bg-[#0866FF] text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
            <InstagramBarChart rows={viewsContent} accent="#0866FF" />
            <p className="mt-4 flex items-center justify-center gap-4 text-xs text-gray-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#0866FF]" />
                Followers
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#60a5fa]" />
                Non-followers
              </span>
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="grid divide-y divide-gray-100 dark:divide-slate-700 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
          <div className="p-6">
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">Profile</h3>
            <div className="mt-5">
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.profile.activity)}
              </p>
              <p className="text-sm text-gray-500">Profile activity</p>
            </div>
            <div className="mt-6 flex items-center justify-between border-t border-gray-100 pt-4 text-sm dark:border-slate-700">
              <span className="text-gray-600 dark:text-slate-400">Profile visits</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {formatNumber(S.profile.visits)}
              </span>
            </div>
          </div>

          <div className="p-6">
            <div className="mb-5">
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.profile.followers)}
              </p>
              <p className="text-sm text-gray-500">Total followers</p>
            </div>
            <div>
              <p className="mb-4 text-sm font-medium text-slate-900 dark:text-slate-100">
                Most active times
              </p>
              <div className="space-y-2.5">
                {S.profile.mostActiveTimes.map((slot) => (
                  <div key={slot.time} className="flex items-center gap-3">
                    <span className="w-8 shrink-0 text-xs text-gray-500">{slot.time}</span>
                    <div className="relative h-5 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
                      <div
                        className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-[#0866FF] to-[#60a5fa]"
                        style={{ width: `${(slot.value / maxActiveTime) * 100}%` }}
                      />
                    </div>
                    <span className="w-6 shrink-0 text-right text-xs font-medium text-slate-900 dark:text-slate-100">
                      {slot.value}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-gray-500">
                <span className="h-2 w-2 rounded-full bg-[#0866FF]" />
                Followers
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="border-b border-gray-100 px-6 py-4 dark:border-slate-700">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">Interactions</h3>
        </div>
        <div className="grid divide-y divide-gray-100 dark:divide-slate-700 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
          <div className="space-y-5 p-6">
            <div>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.interactions.total)}
              </p>
              <p className="text-sm text-gray-500">Interactions</p>
            </div>
            <dl className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <dt className="text-gray-600 dark:text-slate-400">Followers</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {S.interactions.followersPct}%
                </dd>
              </div>
              <div className="flex items-center justify-between text-sm">
                <dt className="text-gray-600 dark:text-slate-400">Non-followers</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {S.interactions.nonFollowersPct}%
                </dd>
              </div>
            </dl>
            <div className="border-t border-gray-100 pt-4 dark:border-slate-700">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 dark:text-slate-400">Accounts engaged</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.interactions.accountsEngaged)}
                </span>
              </div>
            </div>
          </div>

          <div className="p-6">
            <p className="mb-4 text-sm font-medium text-slate-900 dark:text-slate-100">
              By content interactions
            </p>
            <InstagramBarChart rows={S.interactions.byContentType} accent="#0866FF" />
            <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-gray-500">
              <span className="h-2 w-2 rounded-full bg-[#0866FF]" />
              Followers and non-followers
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function InstagramBarChart({
  rows,
  accent,
}: {
  rows: Array<{ label: string; pct: number }>;
  accent: string;
}) {
  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-3">
          <span className="w-14 shrink-0 text-sm text-gray-600 dark:text-slate-400">{row.label}</span>
          <div className="relative h-6 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
            <div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{ width: `${row.pct}%`, backgroundColor: accent }}
            />
          </div>
          <span className="w-12 shrink-0 text-right text-sm font-medium text-slate-900 dark:text-slate-100">
            {row.pct}%
          </span>
        </div>
      ))}
    </div>
  );
}

function FacebookSection() {
  const S = FACEBOOK_STATIC;
  const [insightMetric, setInsightMetric] = useState<'views' | 'engagement' | 'follows'>('views');
  const [contentTab, setContentTab] = useState<'all' | 'reels' | 'posts' | 'stories'>('reels');

  const insightSeries =
    insightMetric === 'views'
      ? S.viewsSeries
      : insightMetric === 'engagement'
        ? S.engagementOverview.series
        : S.viewsSeries.map((point) => ({ ...point, value: Math.max(0, Math.round(point.value / 30)) }));

  const content = S.content[contentTab];
  const contentChartId = `fbContent-${contentTab}`;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Insights</h2>
            <p className="text-sm text-gray-500">Learn how your profile is performing.</p>
          </div>
          <p className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 dark:border-slate-600 dark:text-slate-300">
            {S.dateRange}
          </p>
        </div>

        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <YouTubeMetricTab
            active={insightMetric === 'views'}
            onClick={() => setInsightMetric('views')}
            label="Views"
            value={formatNumber(S.views)}
            status={<TrendLine change={S.viewsChange} label="" className="mt-0" />}
          />
          <YouTubeMetricTab
            active={insightMetric === 'engagement'}
            onClick={() => setInsightMetric('engagement')}
            label="Engagement"
            value={formatNumber(S.engagement)}
            status={<TrendLine change={S.engagementChange} label="" className="mt-0" />}
          />
          <YouTubeMetricTab
            active={insightMetric === 'follows'}
            onClick={() => setInsightMetric('follows')}
            label="Net follows"
            value={formatNumber(S.netFollows)}
            status={<TrendLine change={S.netFollowsChange} label="" className="mt-0" />}
          />
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={insightSeries}>
              <defs>
                <linearGradient id="fbInsights" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#0866FF" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#0866FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={(value: number) => [
                  formatNumber(value),
                  insightMetric === 'views'
                    ? 'Views'
                    : insightMetric === 'engagement'
                      ? 'Engagement'
                      : 'Net follows',
                ]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#0866FF"
                fill="url(#fbInsights)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {(
              [
                { id: 'all' as const, label: 'All views' },
                { id: 'reels' as const, label: 'Reels' },
                { id: 'posts' as const, label: 'Posts' },
                { id: 'stories' as const, label: 'Stories' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setContentTab(tab.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  contentTab === tab.id
                    ? 'bg-[#0866FF] text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <p className="text-sm text-gray-500">{S.dateRange}</p>
        </div>

        {contentTab === 'reels' && (
          <p className="mb-4 text-xs text-gray-500">
            Your insights for reels and previously posted videos are now combined under Reels.
          </p>
        )}

        <div className="mb-6 grid gap-3 sm:grid-cols-2">
          <div
            className={`rounded-lg border p-4 ${
              contentTab === 'reels' || contentTab === 'all' || contentTab === 'posts' || contentTab === 'stories'
                ? 'border-[#0866FF] bg-blue-50/50 dark:bg-blue-950/20'
                : 'border-gray-100 dark:border-slate-700'
            }`}
          >
            <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
              {formatNumber(content.views)}
            </p>
            <p className="text-sm text-gray-500">
              {contentTab === 'posts' ? 'Views' : 'Total views'}
            </p>
            <TrendLine
              change={content.viewsChange}
              label="from previous 28 days"
              className="mt-2"
            />
          </div>
          {contentTab === 'reels' && (
            <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
              <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                {S.content.reels.watchTime}
              </p>
              <p className="text-sm text-gray-500">Watch time</p>
              <TrendLine
                change={S.content.reels.watchTimeChange}
                label="from previous 28 days"
                className="mt-2"
              />
            </div>
          )}
        </div>

        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={content.series}>
              <defs>
                <linearGradient id={contentChartId} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#0866FF" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#0866FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip formatter={(value: number) => [formatNumber(value), 'Views']} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#0866FF"
                fill={`url(#${contentChartId})`}
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Engagement overview
          </h2>
          <p className="text-sm text-gray-500">{S.dateRange}</p>
        </div>

        <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
          {formatNumber(S.engagementOverview.total)}{' '}
          <span className="text-base font-medium text-gray-500">Engagement</span>
        </p>
        <TrendLine
          change={S.engagementOverview.change}
          label="from previous 28 days"
          className="mt-2"
        />

        <div className="mt-6 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={S.engagementOverview.series}>
              <defs>
                <linearGradient id="fbEngage" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#0866FF" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#0866FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip formatter={(value: number) => [formatNumber(value), 'Engagement']} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#0866FF"
                fill="url(#fbEngage)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-[#0866FF] dark:bg-blue-950/40">
              <ThumbsUp className="h-4 w-4" />
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {S.engagementOverview.reactions}
            </p>
            <p className="text-sm text-gray-500">Reactions</p>
          </div>
          <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-[#0866FF] dark:bg-blue-950/40">
              <MessageCircle className="h-4 w-4" />
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {S.engagementOverview.comments}
            </p>
            <p className="text-sm text-gray-500">Comments</p>
          </div>
          <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-[#0866FF] dark:bg-blue-950/40">
              <Share2 className="h-4 w-4" />
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {S.engagementOverview.shares}
            </p>
            <p className="text-sm text-gray-500">Shares</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function LinkedInSection() {
  const S = LINKEDIN_STATIC;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <TrackCard
          value={formatNumber(S.impressions)}
          label="Post impressions in 7 days"
          change={S.impressionsChange}
          compareLabel="vs. prior 7 days"
        />
        <TrackCard
          value={formatNumber(S.followers)}
          label="Total followers"
          change={S.followersChange}
          compareLabel="vs. prior 7 days"
        />
        <TrackCard
          value={formatNumber(S.profileViewers)}
          label="Profile viewers in 90 days"
          change={S.profileViewersChange}
          compareLabel="vs. prior 7 days"
        />
        <TrackCard
          value={formatNumber(S.searchAppearances)}
          label={`Search appearances ${S.searchWindow}`}
          change={S.searchAppearancesChange}
          compareLabel={`vs. ${S.searchCompareWindow}`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Content performance
          </h2>
          <p className="mt-4 text-4xl font-bold text-slate-900 dark:text-slate-100">
            {formatNumber(S.impressions)}{' '}
            <span className="text-base font-medium text-gray-500">Impressions</span>
          </p>
          <TrendLine change={S.impressionsChange} label="vs. prior 7 days" />
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={S.impressionsSeries}>
                <defs>
                  <linearGradient id="liImpr" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#0A66C2" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0A66C2" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => (v >= 1000 ? `${v / 1000}K` : String(v))}
                />
                <Tooltip formatter={(value: number) => [formatNumber(value), 'Impressions']} />
                <Area type="monotone" dataKey="value" stroke="#0A66C2" fill="url(#liImpr)" strokeWidth={2.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-gray-400">Daily data is recorded in UTC</p>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Follower growth</h2>
          <p className="mt-4 text-4xl font-bold text-slate-900 dark:text-slate-100">
            {formatNumber(S.followers)}{' '}
            <span className="text-base font-medium text-gray-500">Total followers</span>
          </p>
          <TrendLine change={S.followersChange} label="vs. prior 7 days" />
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={S.followerGrowthSeries}>
                <defs>
                  <linearGradient id="liFoll" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#0A66C2" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0A66C2" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(value: number) => [formatNumber(value), 'Net new']} />
                <Area type="monotone" dataKey="value" stroke="#0A66C2" fill="url(#liFoll)" strokeWidth={2.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Discovery</h2>
          <dl className="mt-5 space-y-4">
            <StatRow label="Total impressions" value={formatNumber(S.impressions)} />
            <StatRow label="In-network (followers and connections)" value={`${S.inNetworkPct}%`} />
            <StatRow label="Out-of-network" value={`${S.outOfNetworkPct}%`} />
            <StatRow label="Members reached" value={formatNumber(S.membersReached)} />
          </dl>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Engagement</h2>
          <dl className="mt-5 space-y-4">
            <StatRow label="Total social engagements" value={formatNumber(S.socialEngagements)} />
            <EngagementRow icon={<ThumbsUp className="h-4 w-4" />} label="Reactions" value={S.reactions} />
            <EngagementRow icon={<MessageCircle className="h-4 w-4" />} label="Comments" value={S.comments} />
            <EngagementRow icon={<Repeat2 className="h-4 w-4" />} label="Reposts" value={S.reposts} />
            <EngagementRow icon={<Bookmark className="h-4 w-4" />} label="Saves" value={S.saves} />
            <EngagementRow icon={<Send className="h-4 w-4" />} label="Sends on LinkedIn" value={S.sends} />
          </dl>
        </section>
      </div>
    </div>
  );
}

function YouTubeSection() {
  const S = YOUTUBE_STATIC;
  const [channelMetric, setChannelMetric] = useState<'views' | 'watchTime' | 'subscribers'>('views');
  const [contentTab, setContentTab] = useState<'videos' | 'shorts'>('videos');
  const content = contentTab === 'videos' ? S.videos : S.shorts;
  const chartId = contentTab === 'videos' ? 'ytVideos' : 'ytShorts';

  return (
    <div className="space-y-6">
      <p className="text-lg font-medium text-slate-800 dark:text-slate-200">
        Your channel got {formatNumber(S.channelViews)} views in the last 28 days
      </p>

      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Channel analytics
            </h2>
            <p className="text-sm text-gray-500">{S.dateRange} · Last 28 days</p>
          </div>
        </div>

        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <YouTubeMetricTab
            active={channelMetric === 'views'}
            onClick={() => setChannelMetric('views')}
            label="Views"
            value={formatNumber(S.channelViews)}
            status={
              <YouTubeAbsoluteDelta
                delta={S.channelViewsDelta}
                suffix="than usual"
                invertColors
              />
            }
          />
          <YouTubeMetricTab
            active={channelMetric === 'watchTime'}
            onClick={() => setChannelMetric('watchTime')}
            label="Watch time (hours)"
            value={String(S.watchTimeHours)}
            status={<YouTubeFlatStatus label="About the same as usual" />}
          />
          <YouTubeMetricTab
            active={channelMetric === 'subscribers'}
            onClick={() => setChannelMetric('subscribers')}
            label="Subscribers"
            value={formatNumber(S.realtimeSubscribers)}
            status={null}
          />
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={S.channelViewsSeries}>
              <defs>
                <linearGradient id="ytChannel" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#3ea6ff" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#3ea6ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                orientation="right"
                tick={{ fontSize: 11, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip formatter={(value: number) => [formatNumber(value), 'Views']} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#3ea6ff"
                fill="url(#ytChannel)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <UploadMarkers series={S.channelViewsSeries} />
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <div className="mb-5 flex items-center gap-2">
            <Radio className="h-4 w-4 text-sky-500" />
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Realtime</h2>
            <span className="text-xs text-sky-500">● Updating live</span>
          </div>

          <div className="space-y-6">
            <div>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.realtimeSubscribers)}
              </p>
              <p className="mt-1 text-sm text-gray-500">Subscribers</p>
            </div>

            <div className="border-t border-gray-100 pt-5 dark:border-slate-700">
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100">
                {formatNumber(S.realtimeViews48h)}
              </p>
              <p className="mt-1 text-sm text-gray-500">Views · Last 48 hours</p>
              <div className="mt-4 h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={S.realtimeViews48hSeries}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis
                      dataKey="hour"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis hide />
                    <Tooltip formatter={(value: number) => [formatNumber(value), 'Views']} />
                    <Bar dataKey="value" fill="#3ea6ff" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <div className="mb-5 flex flex-wrap gap-2">
            {(
              [
                { id: 'videos' as const, label: 'Videos' },
                { id: 'shorts' as const, label: 'Shorts' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setContentTab(tab.id)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  contentTab === tab.id
                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {contentTab === 'videos' ? 'Video performance' : 'Shorts performance'}
          </h2>
          <p className="text-sm text-gray-500">{S.dateRange} · Last 28 days</p>

          {contentTab === 'videos' ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.videos.views)}
                </p>
                <p className="text-sm text-gray-500">Views</p>
                <YouTubeFlatStatus label="About the same as usual" className="mt-2" />
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">3.7K</p>
                <p className="text-sm text-gray-500">Impressions</p>
                <TrendLine
                  change={S.videos.impressionsChange}
                  label="than previous 28 days"
                  className="mt-2"
                />
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {S.videos.clickThroughRate}%
                </p>
                <p className="text-sm text-gray-500">Impressions click-through rate</p>
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="flex items-center gap-2 text-3xl font-bold text-slate-900 dark:text-slate-100">
                  <Clock className="h-6 w-6 text-gray-400" />
                  {S.videos.avgViewDuration}
                </p>
                <p className="text-sm text-gray-500">Average view duration</p>
              </div>
              <div className="rounded-lg border border-gray-100 p-4 sm:col-span-2 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.realtimeSubscribers)}
                </p>
                <p className="text-sm text-gray-500">Subscribers</p>
              </div>
            </div>
          ) : (
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.shorts.views)}
                </p>
                <p className="text-sm text-gray-500">Views</p>
                <YouTubeAbsoluteDelta
                  delta={S.shorts.viewsDelta}
                  suffix="than usual"
                  invertColors
                />
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.shorts.engagedViews)}
                </p>
                <p className="text-sm text-gray-500">Engaged views</p>
                <TrendLine
                  change={S.shorts.engagedViewsChange}
                  label="than previous 28 days"
                  className="mt-2"
                />
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {S.shorts.likes}
                </p>
                <p className="text-sm text-gray-500">Likes</p>
                <TrendLine
                  change={S.shorts.likesChange}
                  label="than previous 28 days"
                  className="mt-2"
                />
              </div>
              <div className="rounded-lg border border-gray-100 p-4 dark:border-slate-700">
                <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                  {formatNumber(S.realtimeSubscribers)}
                </p>
                <p className="text-sm text-gray-500">Subscribers</p>
              </div>
            </div>
          )}

          <div className="mt-6 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={content.series}>
                <defs>
                  <linearGradient id={chartId} x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#7F56D9" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#7F56D9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  orientation="right"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip formatter={(value: number) => [formatNumber(value), 'Views']} />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#7F56D9"
                  fill={`url(#${chartId})`}
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <UploadMarkers series={content.series} />
        </section>
      </div>
    </div>
  );
}

function YouTubeMetricTab({
  active,
  onClick,
  label,
  value,
  status,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  value: string;
  status: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border p-4 text-left transition ${
        active
          ? 'border-slate-300 bg-slate-50 dark:border-slate-500 dark:bg-slate-900/60'
          : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-750'
      }`}
    >
      <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      <p className="mt-1 text-sm text-gray-500">{label}</p>
      {status && <div className="mt-2">{status}</div>}
    </button>
  );
}

function YouTubeAbsoluteDelta({
  delta,
  suffix,
  invertColors = false,
}: {
  delta: number;
  suffix: string;
  invertColors?: boolean;
}) {
  const positive = delta > 0;
  const flat = delta === 0;
  const good = invertColors ? !positive : positive;
  return (
    <p
      className={`flex items-center gap-1 text-sm ${
        flat ? 'text-gray-500' : good ? 'text-emerald-600' : 'text-red-600'
      }`}
    >
      {flat ? (
        <span className="inline-block h-2 w-2 rounded-full bg-gray-400" />
      ) : positive ? (
        <ArrowUp className="h-3.5 w-3.5" />
      ) : (
        <ArrowDown className="h-3.5 w-3.5" />
      )}
      <span>
        {flat ? 'No change' : `${Math.abs(delta)} ${positive ? 'more' : 'less'}`} {suffix}
      </span>
    </p>
  );
}

function YouTubeFlatStatus({ label, className = '' }: { label: string; className?: string }) {
  return (
    <p className={`flex items-center gap-1.5 text-sm text-gray-500 ${className}`}>
      <Check className="h-3.5 w-3.5 text-emerald-500" />
      {label}
    </p>
  );
}

function UploadMarkers({ series }: { series: Array<{ date: string; upload?: boolean }> }) {
  const uploads = series.filter((point) => point.upload);
  if (uploads.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-400">
      {uploads.map((point) => (
        <span key={point.date} className="inline-flex items-center gap-1">
          <Play className="h-3 w-3" />
          {point.date}
        </span>
      ))}
    </div>
  );
}

function TrackCard({
  value,
  label,
  change,
  compareLabel,
}: {
  value: string;
  label: string;
  change: number;
  compareLabel: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">{label}</p>
      <TrendLine change={change} label={compareLabel} className="mt-3" />
    </div>
  );
}

function TrendLine({
  change,
  label,
  className = 'mt-2',
}: {
  change: number;
  label: string;
  className?: string;
}) {
  const positive = change > 0;
  const flat = change === 0;
  return (
    <p
      className={`${className} flex items-center gap-1 text-sm ${
        flat ? 'text-gray-500' : positive ? 'text-emerald-600' : 'text-red-600'
      }`}
    >
      {flat ? (
        <span className="inline-block h-2 w-2 rounded-full bg-gray-400" />
      ) : (
        <ArrowUp className={`h-3.5 w-3.5 ${positive ? '' : 'rotate-180'}`} />
      )}
      <span className="font-medium">{new Intl.NumberFormat('en-US').format(change)}%</span>
      <span className="text-gray-500">{label}</span>
    </p>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3 last:border-0 last:pb-0 dark:border-slate-700">
      <dt className="text-sm text-gray-600 dark:text-slate-400">{label}</dt>
      <dd className="text-sm font-semibold text-slate-900 dark:text-slate-100">{value}</dd>
    </div>
  );
}

function EngagementRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-3 last:border-0 last:pb-0 dark:border-slate-700">
      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-slate-400">
        <span className="text-gray-400">{icon}</span>
        {label}
      </div>
      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {formatNumber(value)}
      </span>
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
