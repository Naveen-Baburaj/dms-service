'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock, ExternalLink, Loader2, RefreshCw, Search } from 'lucide-react';

import { cn } from '@/lib/utils';
import { listRpaContacts, type RpaSavedContact } from '@/services/api/rpaGhl';

function clean(value: unknown): string {
  if (value == null || value === '') return '-';
  return String(value);
}

function formatDateTime(value?: string): string {
  if (!value) return '-';
  const date = new Date(value.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

function statusTone(status?: string): {
  icon: typeof CheckCircle2;
  className: string;
} {
  const normalized = (status || '').toLowerCase();

  if (normalized.includes('success') || normalized.includes('synced') || normalized.includes('verified')) {
    return {
      icon: CheckCircle2,
      className: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    };
  }

  if (normalized.includes('fail') || normalized.includes('error')) {
    return {
      icon: AlertCircle,
      className: 'border-red-500/20 bg-red-500/10 text-red-600',
    };
  }

  return {
    icon: Clock,
    className: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
  };
}

export function RpaSavedContactsTable({
  role,
  company,
  refreshSignal = 0,
}: {
  role: string;
  company: string;
  refreshSignal?: number;
}) {
  const [rows, setRows] = useState<RpaSavedContact[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canLoad = useMemo(() => Boolean(role && company), [role, company]);

  const loadContacts = useCallback(async (query?: string) => {
    if (!canLoad) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await listRpaContacts({
        role,
        company,
        limit: 25,
        search: query ?? search,
      });
      setRows(data.rows ?? []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load saved contacts.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [canLoad, company, role, search]);

  useEffect(() => {
    void loadContacts('');
    // refreshSignal intentionally reloads after successful saves from the parent panel.
  }, [loadContacts, refreshSignal]);

  function submitSearch() {
    void loadContacts(search);
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-semibold text-foreground">Saved Contacts</h2>
          <p className="text-xs text-muted-foreground">
            Backend records with DMS IDs, RPA job IDs, and GoHighLevel sync status.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') submitSearch();
              }}
              placeholder="Search contact, email, phone, job"
              className="w-full rounded-xl border border-border bg-background py-2 pl-8 pr-3 text-xs outline-none transition focus:border-violet-500 sm:w-64"
            />
          </div>
          <button
            type="button"
            onClick={() => submitSearch()}
            disabled={isLoading}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-border px-3 py-2 text-xs font-medium text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] text-xs">
          <thead>
            <tr className="border-b border-border/60 text-left text-muted-foreground">
              <th className="pb-2 pr-3 font-medium">Contact</th>
              <th className="pb-2 pr-3 font-medium">Email</th>
              <th className="pb-2 pr-3 font-medium">Phone</th>
              <th className="pb-2 pr-3 font-medium">Target</th>
              <th className="pb-2 pr-3 font-medium">GHL Sync</th>
              <th className="pb-2 pr-3 font-medium">DMS Contact</th>
              <th className="pb-2 pr-3 font-medium">RPA Job</th>
              <th className="pb-2 pr-3 font-medium">Modified</th>
              <th className="pb-2 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !isLoading ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-muted-foreground">
                  No saved RPA contacts found yet.
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const tone = statusTone(row.ghl_sync_status);
                const StatusIcon = tone.icon;
                return (
                  <tr key={row.name} className="border-b border-border/40 align-top last:border-0">
                    <td className="py-3 pr-3">
                      <div className="font-semibold text-foreground">{clean(row.contact_name || `${row.first_name ?? ''} ${row.last_name ?? ''}`.trim())}</div>
                      <div className="mt-0.5 text-muted-foreground">{clean(row.vehicle_interest)}</div>
                    </td>
                    <td className="py-3 pr-3 text-muted-foreground">{clean(row.email)}</td>
                    <td className="py-3 pr-3 font-mono text-muted-foreground">{clean(row.phone)}</td>
                    <td className="py-3 pr-3">
                      <span className="rounded-full border border-border bg-background px-2 py-1 text-[11px] font-medium text-foreground">
                        {clean(row.save_target)}
                      </span>
                    </td>
                    <td className="py-3 pr-3">
                      <div className={cn('inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-semibold', tone.className)}>
                        <StatusIcon className="h-3 w-3" />
                        {clean(row.ghl_sync_status)}
                      </div>
                      {row.ghl_sync_message && (
                        <div className="mt-1 max-w-[220px] truncate text-muted-foreground" title={row.ghl_sync_message}>
                          {row.ghl_sync_message}
                        </div>
                      )}
                    </td>
                    <td className="py-3 pr-3 font-mono text-[11px] text-muted-foreground">{row.name}</td>
                    <td className="py-3 pr-3 font-mono text-[11px] text-muted-foreground">{clean(row.rpa_job)}</td>
                    <td className="py-3 pr-3 text-muted-foreground">
                      <div>{formatDateTime(row.modified)}</div>
                      {row.last_synced_at && <div className="mt-0.5">Synced: {formatDateTime(row.last_synced_at)}</div>}
                    </td>
                    <td className="py-3 text-right">
                      {row.ghl_contact_url ? (
                        <a
                          href={row.ghl_contact_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center justify-end gap-1 text-violet-600 hover:underline"
                        >
                          Open GHL
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-5 text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading saved contacts...
          </div>
        )}
      </div>
    </div>
  );
}
