'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import toast from 'react-hot-toast';
import {
  AlertCircle,
  BarChart3,
  Globe,
  Instagram,
  Lightbulb,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  TrendingUp,
  X,
  Youtube,
} from 'lucide-react';

import { API_ENDPOINTS, apiFetch, fetchWithTimeout } from '@/lib/api-client';
import type {
  Rival,
  RivalCreate,
  RivalInsightsResponse,
  RivalsConfigResponse,
  RivalSnapshot,
} from '@/lib/types';

const PLATFORM_META: Record<
  string,
  { label: string; icon: ReactNode; accent: string }
> = {
  youtube: { label: 'YouTube', icon: <Youtube className="h-4 w-4" />, accent: 'text-red-600' },
  instagram: { label: 'Instagram', icon: <Instagram className="h-4 w-4" />, accent: 'text-pink-600' },
  website: { label: 'Website', icon: <Globe className="h-4 w-4" />, accent: 'text-emerald-600' },
};

const emptyForm: RivalCreate = {
  name: '',
  category: 'spice',
  website: '',
  youtube_handle: '',
  youtube_channel_id: '',
  instagram_username: '',
  rss_url: '',
  notes: '',
  is_active: true,
};

function formatNumber(value?: number | string | null): string {
  if (value === null || value === undefined || value === '') return '-';
  const num = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(num)) return String(value);
  return new Intl.NumberFormat('en-US', {
    notation: num >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(num);
}

function statusBadge(status?: string) {
  switch (status) {
    case 'ok':
      return 'bg-green-100 text-green-700 dark:bg-emerald-950/50 dark:text-emerald-300';
    case 'unavailable':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300';
    case 'error':
      return 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300';
    default:
      return 'bg-gray-100 text-gray-500 dark:bg-slate-700 dark:text-slate-400';
  }
}

function priorityBadge(priority: string) {
  switch (priority) {
    case 'high':
      return 'bg-red-100 text-red-700 border-red-200 dark:bg-red-950/50 dark:text-red-300 dark:border-red-800';
    case 'medium':
      return 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800';
    default:
      return 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800';
  }
}

export default function RivalReviewPage() {
  const [rivals, setRivals] = useState<Rival[]>([]);
  const [rivalsConfig, setRivalsConfig] = useState<RivalsConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshingId, setRefreshingId] = useState<number | null>(null);
  const [refreshingAll, setRefreshingAll] = useState(false);

  const [insights, setInsights] = useState<RivalInsightsResponse | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const [modal, setModal] = useState<{ open: boolean; editId: number | null }>({
    open: false,
    editId: null,
  });
  const [form, setForm] = useState<RivalCreate>(emptyForm);
  const [saving, setSaving] = useState(false);

  const [trendRival, setTrendRival] = useState<Rival | null>(null);

  const loadRivals = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    try {
      if (!silent) {
        setIsLoading(true);
        setError(null);
      }
      // Skip server-side auto-refresh so the list returns immediately.
      // Use Refresh / Refresh all to pull YouTube / IG / website stats.
      const res = await fetchWithTimeout(`${API_ENDPOINTS.RIVALS}?auto_refresh=false`, {
        timeoutMs: 30000,
      });
      if (!res.ok) throw new Error(`Failed to load rivals (${res.status})`);
      setRivals((await res.json()) as Rival[]);
      if (silent) setError(null);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : 'Failed to load rivals');
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRivals();
    fetchWithTimeout(API_ENDPOINTS.RIVALS_CONFIG)
      .then(async (res) => {
        if (res.ok) setRivalsConfig((await res.json()) as RivalsConfigResponse);
      })
      .catch(() => {
        /* non-fatal */
      });
  }, [loadRivals]);

  const handleRefresh = async (id: number) => {
    setRefreshingId(id);
    try {
      const res = await apiFetch(API_ENDPOINTS.RIVAL_REFRESH(id), { method: 'POST' });
      if (!res.ok) throw new Error(`Refresh failed (${res.status})`);
      const updated = (await res.json()) as Rival;
      setRivals((prev) => prev.map((r) => (r.id === id ? updated : r)));
      toast.success(`Updated ${updated.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Refresh failed');
    } finally {
      setRefreshingId(null);
    }
  };

  const handleRefreshAll = async () => {
    setRefreshingAll(true);
    const pending = toast.loading('Refreshing all rivals...');
    try {
      const res = await apiFetch(API_ENDPOINTS.RIVALS_REFRESH_ALL, { method: 'POST' });
      if (!res.ok) throw new Error(`Refresh failed (${res.status})`);
      await loadRivals({ silent: true });
      toast.success('All rivals refreshed', { id: pending });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Refresh failed', { id: pending });
    } finally {
      setRefreshingAll(false);
    }
  };

  const handleGetInsights = async () => {
    setInsightsLoading(true);
    const pending = toast.loading('Analyzing rivals with AI...');
    try {
      // Gemini can take ~30–90s; give headroom but fail with a clear message.
      const res = await fetchWithTimeout(API_ENDPOINTS.RIVALS_INSIGHTS, {
        timeoutMs: 120000,
      });
      if (!res.ok) throw new Error(`Insights failed (${res.status})`);
      const data = (await res.json()) as RivalInsightsResponse;
      setInsights(data);
      if (data.suggestions.length) {
        const top = data.suggestions[0];
        toast.success(`Top tip: ${top.recommendation}`, { id: pending, duration: 6000 });
      } else {
        toast(data.message || 'No suggestions generated', { id: pending });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Insights failed', { id: pending });
    } finally {
      setInsightsLoading(false);
    }
  };

  const openAdd = () => {
    setForm(emptyForm);
    setModal({ open: true, editId: null });
  };

  const openEdit = (rival: Rival) => {
    setForm({
      name: rival.name,
      category: rival.category ?? '',
      website: rival.website ?? '',
      youtube_handle: rival.youtube_handle ?? '',
      youtube_channel_id: rival.youtube_channel_id ?? '',
      instagram_username: rival.instagram_username ?? '',
      rss_url: rival.rss_url ?? '',
      notes: rival.notes ?? '',
      is_active: rival.is_active,
    });
    setModal({ open: true, editId: rival.id });
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('Name is required');
      return;
    }
    setSaving(true);
    try {
      const isEdit = modal.editId !== null;
      const url = isEdit ? API_ENDPOINTS.RIVAL_DETAIL(modal.editId as number) : API_ENDPOINTS.RIVALS;
      const res = await apiFetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      const saved = (await res.json()) as Rival;
      setRivals((prev) =>
        isEdit ? prev.map((r) => (r.id === saved.id ? saved : r)) : [...prev, saved]
      );
      toast.success(isEdit ? 'Rival updated' : 'Rival added');
      setModal({ open: false, editId: null });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (rival: Rival) => {
    if (!window.confirm(`Remove ${rival.name} from Rival Review?`)) return;
    try {
      const res = await apiFetch(API_ENDPOINTS.RIVAL_DETAIL(rival.id), { method: 'DELETE' });
      if (!res.ok) throw new Error(`Delete failed (${res.status})`);
      setRivals((prev) => prev.filter((r) => r.id !== rival.id));
      toast.success(`Removed ${rival.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  return (
    <div className="max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Rival Review</h1>
          <p className="mt-1 text-gray-600">
            Track top Pakistani exporters, see how they perform, and get AI tips on
            what they do better than us.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
          >
            <Plus className="h-4 w-4" /> Add Rival
          </button>
          <button
            onClick={handleRefreshAll}
            disabled={refreshingAll}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${refreshingAll ? 'animate-spin' : ''}`} />
            Refresh all
          </button>
          <button
            onClick={handleGetInsights}
            disabled={insightsLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:opacity-60"
          >
            <Sparkles className="h-4 w-4" /> Get AI suggestions
          </button>
        </div>
      </div>

      {rivalsConfig && (
        <RivalsConfigPanel config={rivalsConfig} />
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      )}

      {insights && (
        <InsightsPanel insights={insights} onClose={() => setInsights(null)} />
      )}

      {isLoading ? (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-gray-500 shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <span className="inline-block w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p>Loading rivals…</p>
        </div>
      ) : rivals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-10 text-center text-gray-600">
          No rivals yet. Click <span className="font-medium">Add Rival</span> to start tracking competitors.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rivals.map((rival) => (
            <RivalCard
              key={rival.id}
              rival={rival}
              refreshing={refreshingId === rival.id}
              onRefresh={() => handleRefresh(rival.id)}
              onEdit={() => openEdit(rival)}
              onDelete={() => handleDelete(rival)}
              onTrends={() => setTrendRival(rival)}
            />
          ))}
        </div>
      )}

      {modal.open && (
        <RivalFormModal
          form={form}
          setForm={setForm}
          saving={saving}
          isEdit={modal.editId !== null}
          onClose={() => setModal({ open: false, editId: null })}
          onSave={handleSave}
        />
      )}

      {trendRival && (
        <TrendModal rival={trendRival} onClose={() => setTrendRival(null)} />
      )}
    </div>
  );
}

function RivalsConfigPanel({ config }: { config: RivalsConfigResponse }) {
  const items = [
    { key: 'youtube', label: 'YouTube', icon: <Youtube className="h-4 w-4" />, data: config.youtube },
    { key: 'instagram', label: 'Instagram', icon: <Instagram className="h-4 w-4" />, data: config.instagram },
    { key: 'website', label: 'Website / RSS', icon: <Globe className="h-4 w-4" />, data: config.website },
  ] as const;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Data source configuration</h2>
      <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
        Rival Review uses separate keys from Content Posting. After updating backend <code>.env</code>, restart the server and click <strong>Refresh all</strong>.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {items.map(({ key, label, icon, data }) => (
          <div
            key={key}
            className={`rounded-lg border px-4 py-3 ${
              data.configured
                ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-800/60 dark:bg-emerald-950/30'
                : 'border-amber-200 bg-amber-50 dark:border-amber-800/60 dark:bg-amber-950/30'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium text-slate-800 dark:text-slate-100">
                {icon}
                {label}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  data.configured
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300'
                }`}
              >
                {data.configured ? 'Ready' : 'Not ready'}
              </span>
            </div>
            <p className="mt-2 text-xs text-gray-600 dark:text-slate-400">{data.hint}</p>
            {key === 'youtube' && data.configured && data.auth_mode === 'oauth' && (
              <p className="mt-1 text-[11px] text-gray-500 dark:text-slate-500">
                Using YouTube OAuth (upload credentials) because <code>YOUTUBE_DATA_API_KEY</code> is empty.
              </p>
            )}
            {key === 'instagram' && !data.configured && (
              <a
                href={API_ENDPOINTS.META_AUTH}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex text-xs font-semibold text-pink-700 underline underline-offset-2 hover:text-pink-800 dark:text-pink-300"
              >
                Reconnect Meta (Facebook / Instagram)
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function RivalCard({
  rival,
  refreshing,
  onRefresh,
  onEdit,
  onDelete,
  onTrends,
}: {
  rival: Rival;
  refreshing: boolean;
  onRefresh: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTrends: () => void;
}) {
  const yt = rival.platforms.youtube;
  const ig = rival.platforms.instagram;
  const web = rival.platforms.website;

  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{rival.name}</h2>
          {rival.category && (
            <span className="mt-1 inline-block rounded-full bg-gold-50 px-2 py-0.5 text-xs font-medium text-gold-700 border border-gold-200 capitalize dark:bg-gold-950/40 dark:text-gold-300 dark:border-gold-800/60">
              {rival.category}
            </span>
          )}
        </div>
        <div className="flex gap-1">
          <IconButton title="Trends" onClick={onTrends}>
            <TrendingUp className="h-4 w-4" />
          </IconButton>
          <IconButton title="Refresh" onClick={onRefresh} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          </IconButton>
          <IconButton title="Edit" onClick={onEdit}>
            <Pencil className="h-4 w-4" />
          </IconButton>
          <IconButton title="Delete" onClick={onDelete}>
            <Trash2 className="h-4 w-4 text-red-500" />
          </IconButton>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Metric
          label="YT subscribers"
          value={formatNumber(yt?.metrics?.subscribers as number)}
          hint={yt?.status !== 'ok' ? yt?.message : undefined}
        />
        <Metric
          label="YT total views"
          value={formatNumber(yt?.metrics?.total_views as number)}
          hint={yt?.status !== 'ok' ? yt?.message : undefined}
        />
        <Metric label="IG followers" value={formatNumber(ig?.metrics?.followers as number)} hint={ig?.status !== 'ok' ? ig?.message : undefined} />
        <Metric
          label="IG avg engagement"
          value={formatNumber(ig?.metrics?.recent_avg_engagement as number)}
          hint={ig?.status !== 'ok' ? ig?.message : undefined}
        />
      </div>

      <div className="mt-4 space-y-1.5">
        <PlatformStatusRow platform="youtube" snapshot={yt} />
        <PlatformStatusRow platform="instagram" snapshot={ig} />
        <PlatformStatusRow platform="website" snapshot={web} />
      </div>

      <p className="mt-4 text-xs text-gray-400">
        {rival.last_refreshed_at
          ? `Last refreshed ${new Date(rival.last_refreshed_at).toLocaleString()}`
          : 'Not refreshed yet - click the refresh icon.'}
      </p>
    </div>
  );
}

function PlatformStatusRow({
  platform,
  snapshot,
}: {
  platform: string;
  snapshot?: RivalSnapshot;
}) {
  const meta = PLATFORM_META[platform];
  return (
    <div className="flex items-center justify-between text-sm">
      <span className={`flex items-center gap-1.5 font-medium ${meta.accent}`}>
        {meta.icon}
        {meta.label}
      </span>
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(snapshot?.status)}`}
        title={snapshot?.message ?? undefined}
      >
        {snapshot?.status ?? 'not refreshed'}
      </span>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string | null }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-slate-900/60" title={hint ?? undefined}>
      <p className="text-xs text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-gray-900 dark:text-slate-100">{value}</p>
      {hint && value === '-' && (
        <p className="mt-1 text-[10px] leading-tight text-amber-700 dark:text-amber-300 line-clamp-2">
          {hint}
        </p>
      )}
    </div>
  );
}

function IconButton({
  children,
  title,
  onClick,
  disabled,
}: {
  children: ReactNode;
  title: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-gray-800 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function InsightsPanel({
  insights,
  onClose,
}: {
  insights: RivalInsightsResponse;
  onClose: () => void;
}) {
  return (
    <div className="rounded-xl border border-brand-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-gold-500" />
          <h2 className="text-xl font-semibold text-gray-900">AI Suggestions</h2>
          <span className="text-sm text-gray-400">
            from {insights.rival_count} rival{insights.rival_count === 1 ? '' : 's'}
          </span>
        </div>
        <IconButton title="Dismiss" onClick={onClose}>
          <X className="h-4 w-4" />
        </IconButton>
      </div>

      {insights.suggestions.length === 0 ? (
        <p className="text-sm text-gray-600">
          {insights.message || 'No suggestions were generated.'}
          {insights.raw && (
            <span className="mt-2 block whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-xs text-gray-500">
              {insights.raw}
            </span>
          )}
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {insights.suggestions.map((s, idx) => (
            <div key={idx} className="rounded-lg border border-gray-200 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">{s.rival}</span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${priorityBadge(s.priority)}`}
                >
                  {s.priority} · {s.platform}
                </span>
              </div>
              <p className="text-sm text-gray-700">
                <span className="font-medium">They:</span> {s.observation}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                <span className="font-medium">Edge:</span> {s.why_better}
              </p>
              <p className="mt-2 rounded-md bg-brand-50 px-3 py-2 text-sm text-brand-900">
                <span className="font-semibold">Do this:</span> {s.recommendation}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RivalFormModal({
  form,
  setForm,
  saving,
  isEdit,
  onClose,
  onSave,
}: {
  form: RivalCreate;
  setForm: (f: RivalCreate) => void;
  saving: boolean;
  isEdit: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  const update = (key: keyof RivalCreate, value: string | boolean) =>
    setForm({ ...form, [key]: value });

  return (
    <Modal title={isEdit ? 'Edit rival' : 'Add rival'} onClose={onClose}>
      <div className="space-y-3">
        <Field label="Name *">
          <input
            className="input"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            placeholder="Shan Foods"
          />
        </Field>
        <Field label="Category">
          <select
            className="input"
            value={form.category ?? ''}
            onChange={(e) => update('category', e.target.value)}
          >
            <option value="spice">Spice</option>
            <option value="rice">Rice</option>
            <option value="chutney">Chutney</option>
            <option value="mixed">Mixed</option>
          </select>
        </Field>
        <Field label="Website">
          <input
            className="input"
            value={form.website ?? ''}
            onChange={(e) => update('website', e.target.value)}
            placeholder="https://www.shanfoods.com"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="YouTube handle">
            <input
              className="input"
              value={form.youtube_handle ?? ''}
              onChange={(e) => update('youtube_handle', e.target.value)}
              placeholder="@ShanFoodsGlobal"
            />
          </Field>
          <Field label="YouTube channel ID">
            <input
              className="input"
              value={form.youtube_channel_id ?? ''}
              onChange={(e) => update('youtube_channel_id', e.target.value)}
              placeholder="UC..."
            />
          </Field>
        </div>
        <Field label="Instagram username">
          <input
            className="input"
            value={form.instagram_username ?? ''}
            onChange={(e) => update('instagram_username', e.target.value)}
            placeholder="shanfoodsglobal"
          />
        </Field>
        <Field label="RSS feed URL (optional)">
          <input
            className="input"
            value={form.rss_url ?? ''}
            onChange={(e) => update('rss_url', e.target.value)}
            placeholder="https://example.com/feed"
          />
        </Field>
        <Field label="Notes">
          <textarea
            className="input"
            rows={2}
            value={form.notes ?? ''}
            onChange={(e) => update('notes', e.target.value)}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={form.is_active ?? true}
            onChange={(e) => update('is_active', e.target.checked)}
          />
          Active (included in refresh-all and AI suggestions)
        </label>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <button
          onClick={onClose}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="rounded-lg bg-brand-900 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800 disabled:opacity-60"
        >
          {saving ? 'Saving...' : isEdit ? 'Save changes' : 'Add rival'}
        </button>
      </div>

      <style jsx>{`
        :global(.input) {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid #e5e7eb;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          outline: none;
        }
        :global(.input:focus) {
          border-color: #9ca3af;
        }
      `}</style>
    </Modal>
  );
}

function TrendModal({ rival, onClose }: { rival: Rival; onClose: () => void }) {
  const [snapshots, setSnapshots] = useState<RivalSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [platform, setPlatform] = useState<'youtube' | 'instagram'>('youtube');

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        const res = await apiFetch(API_ENDPOINTS.RIVAL_SNAPSHOTS(rival.id));
        if (!res.ok) throw new Error('Failed to load history');
        const data = (await res.json()) as RivalSnapshot[];
        if (active) setSnapshots(data);
      } catch {
        if (active) setSnapshots([]);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [rival.id]);

  const series = useMemo(() => {
    const audienceKey = platform === 'youtube' ? 'subscribers' : 'followers';
    return snapshots
      .filter((s) => s.platform === platform && s.status === 'ok')
      .slice()
      .reverse()
      .map((s) => ({
        date: s.captured_at ? new Date(s.captured_at).toLocaleDateString() : '',
        audience: Number(s.metrics?.[audienceKey] ?? 0),
        engagement: Number(s.metrics?.recent_avg_engagement ?? 0),
      }));
  }, [snapshots, platform]);

  return (
    <Modal title={`${rival.name} - trends`} onClose={onClose} wide>
      <div className="mb-4 flex gap-2">
        {(['youtube', 'instagram'] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPlatform(p)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition ${
              platform === p ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex h-72 items-center justify-center text-gray-500">Loading history...</div>
      ) : series.length < 2 ? (
        <div className="flex h-72 flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-center text-sm text-gray-600">
          <BarChart3 className="mb-2 h-8 w-8 text-gray-300" />
          Not enough history yet. Refresh this rival a few times to build a trend.
        </div>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="audience"
                name={platform === 'youtube' ? 'Subscribers' : 'Followers'}
                stroke="#7f1d1d"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="engagement"
                name="Avg engagement"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Modal>
  );
}

function Modal({
  title,
  children,
  onClose,
  wide,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className={`w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} max-h-[90vh] overflow-y-auto rounded-xl bg-white p-6 shadow-xl`}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
          <IconButton title="Close" onClick={onClose}>
            <X className="h-5 w-5" />
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      {children}
    </label>
  );
}
