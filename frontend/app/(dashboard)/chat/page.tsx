'use client';
import { useState, useRef, useEffect } from 'react';
import {
  Send, Plus, Bot, Sparkles, Car, TrendingUp,
  Users,
  Paperclip, Mic, RotateCcw, ThumbsUp, ThumbsDown, Copy,
  MessageSquare, Clock, Star, AlertCircle,
  PhoneCall, Workflow, Database, Cloud, CheckCircle2, Loader2, ShieldCheck,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';
import type { User } from '@/types';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { RpaSavedContactsTable } from '@/components/rpa/RpaSavedContactsTable';
import { queryDashboardAgent, type AgentResponse, type FiltersApplied } from '@/services/api/aiAgent';
import { checkGhlSession, openGhlLogin, saveRpaContact, type RpaContactPayload, type RpaSaveResult, type RpaSaveTarget } from '@/services/api/rpaGhl';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agentData?: AgentResponse;
  error?: boolean;
}


const SUGGESTED_PROMPTS = [
  { icon: TrendingUp, label: "What was the sales in the last 5 months?", color: 'text-emerald-500' },
  { icon: Users, label: "Show me service records for the last 3 months", color: 'text-blue-500' },
  { icon: Car, label: "What is the current inventory stock?", color: 'text-orange-500' },
  { icon: MessageSquare, label: "Compare sales across all tenants", color: 'text-purple-500' },
];


type WorkspaceModule = 'chat' | 'voice' | 'rpa';

type RpaPhase = 'idle' | 'validating' | 'session' | 'login' | 'saving' | 'syncing' | 'success' | 'error';

interface RpaProgressState {
  phase: RpaPhase;
  percent: number;
  label: string;
  detail: string;
}

const RPA_TARGETS: { value: RpaSaveTarget; label: string; description: string; icon: typeof Database }[] = [
  {
    value: 'dms',
    label: 'DMS Backend',
    description: 'Save locally in Frappe/DMS only.',
    icon: Database,
  },
  {
    value: 'ghl',
    label: 'GHL CRM',
    description: 'Create in GoHighLevel only.',
    icon: Cloud,
  },
  {
    value: 'both',
    label: 'Both',
    description: 'Save in DMS first, then sync to GHL CRM.',
    icon: Workflow,
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}


function resolveRole(user: User | null): string {
  return user?.role ?? '';
}

function resolveCompany(user: User | null): string {
  return user?.company ?? '';
}

// ─── Widget payloads ──────────────────────────────────────────────────────────
interface SalesChartPayload {
  labels: string[];
  series: number[];
  total?: number;
  highest_month?: { month: string; sales: number };
}

interface ServiceCountPayload {
  labels: string[];
  series: number[];
  total?: number;
}

interface InventoryRow {
  tenant_id?: string;
  tenant_name?: string;
  category?: string;
  stock?: number;
  vehicle_name?: string;
  model?: string;
  variant?: string;
  stock_status?: string;
}

interface InventoryPayload {
  rows: InventoryRow[];
  total_stock?: number;
  low_stock_items?: InventoryRow[];
  status_counts?: Record<string, number>;
}


interface RecordTableColumn {
  key: string;
  label: string;
}

interface RecordTablePayload {
  title: string;
  resource: string;
  doctype: string;
  columns: RecordTableColumn[];
  rows: Record<string, unknown>[];
  total: number;
  data_source?: string;
}


interface GenericChartSpec {
  id: string;
  title: string;
  description?: string;
  type: 'bar' | 'line';
  labels: string[];
  series: number[];
  total?: number;
  prefix?: string;
  suffix?: string;
}

interface GenericChartsPayload {
  title: string;
  scope: string;
  month_limit: number;
  charts: GenericChartSpec[];
  data_source?: string;
}

interface TenantComparisonPayload {
  labels: string[];
  series: number[];
}

// ─── Widget components ────────────────────────────────────────────────────────
function SalesChartWidget({ payload }: { payload: unknown }) {
  const p = payload as SalesChartPayload;
  const data = (p.labels ?? []).map((label, i) => ({
    month: label,
    Sales: p.series?.[i] ?? 0,
  }));

  if (!data.length) return (
    <div className="mt-3 rounded-xl border border-border/50 bg-muted/30 p-4 text-xs text-muted-foreground text-center">
      No sales data available for this period.
    </div>
  );

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">Sales Chart</p>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="salesGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="month" tick={{ fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} width={44} />
          <Tooltip
            formatter={(v: number) => [`₹${v.toLocaleString()}`, 'Sales']}
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
          />
          <Area type="monotone" dataKey="Sales" stroke="#7c3aed" fill="url(#salesGrad)" strokeWidth={2} dot={{ r: 3, fill: '#7c3aed' }} />
        </AreaChart>
      </ResponsiveContainer>
      {p.total != null && (
        <p className="mt-2 text-[11px] text-muted-foreground text-right">
          Total: <span className="font-semibold text-foreground">₹{p.total.toLocaleString()}</span>
          {p.highest_month && (
            <> · Peak: <span className="font-semibold text-foreground">{p.highest_month.month}</span></>
          )}
        </p>
      )}
    </div>
  );
}

function ServiceCountWidget({ payload }: { payload: unknown }) {
  const p = payload as ServiceCountPayload;
  const data = (p.labels ?? []).map((label, i) => ({
    month: label,
    'Service Jobs': p.series?.[i] ?? 0,
  }));

  if (!data.length) return (
    <div className="mt-3 rounded-xl border border-border/50 bg-muted/30 p-4 text-xs text-muted-foreground text-center">
      No service data available.
    </div>
  );

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">Service Count</p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="month" tick={{ fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} width={32} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
          <Bar dataKey="Service Jobs" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {p.total != null && (
        <p className="mt-2 text-[11px] text-muted-foreground text-right">
          Total jobs: <span className="font-semibold text-foreground">{p.total.toLocaleString()}</span>
        </p>
      )}
    </div>
  );
}

function InventoryTableWidget({ payload }: { payload: unknown }) {
  const p = payload as InventoryPayload;
  const rows = p.rows ?? [];
  const hasVehicleRows = rows.some((row) => row.vehicle_name || row.model || row.variant || row.stock_status);
  const showTenant = rows.some((row) => row.tenant_id !== undefined || row.tenant_name !== undefined);

  function clean(value: unknown): string {
    if (value == null || value === '') return '-';
    return String(value).replace(/_/g, ' ');
  }

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Inventory
        {p.total_stock != null && (
          <span className="ml-2 font-normal text-foreground">
            ({p.total_stock.toLocaleString()} {hasVehicleRows ? 'vehicle record(s)' : 'total units'})
          </span>
        )}
      </p>

      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-2">No inventory data.</p>
      ) : hasVehicleRows ? (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/50">
              {showTenant && <th className="text-left pb-1.5 font-medium text-muted-foreground">Tenant</th>}
              <th className="text-left pb-1.5 font-medium text-muted-foreground">Vehicle</th>
              <th className="text-left pb-1.5 font-medium text-muted-foreground">Model</th>
              <th className="text-left pb-1.5 font-medium text-muted-foreground">Variant</th>
              <th className="text-right pb-1.5 font-medium text-muted-foreground">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const status = clean(row.stock_status);
              const isAvailable = status.toLowerCase() === 'in stock' || status.toLowerCase() === 'available';

              return (
                <tr key={i} className="border-b border-border/30 last:border-0">
                  {showTenant && (
                    <td className="py-1.5 capitalize text-muted-foreground">{clean(row.tenant_name ?? row.tenant_id)}</td>
                  )}
                  <td className="py-1.5">{clean(row.vehicle_name ?? row.category)}</td>
                  <td className="py-1.5">{clean(row.model)}</td>
                  <td className="py-1.5">{clean(row.variant)}</td>
                  <td className="py-1.5 text-right">
                    <span className={cn(
                      'inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                      isAvailable ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600',
                    )}>
                      {status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/50">
              {showTenant && <th className="text-left pb-1.5 font-medium text-muted-foreground">Tenant</th>}
              <th className="text-left pb-1.5 font-medium text-muted-foreground">Category</th>
              <th className="text-right pb-1.5 font-medium text-muted-foreground">Stock</th>
              <th className="text-right pb-1.5 font-medium text-muted-foreground">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const stock = Number(row.stock ?? 0);
              const isLow = stock < 100;

              return (
                <tr key={i} className="border-b border-border/30 last:border-0">
                  {showTenant && (
                    <td className="py-1.5 capitalize text-muted-foreground">{clean(row.tenant_name ?? row.tenant_id)}</td>
                  )}
                  <td className="py-1.5 capitalize">{clean(row.category)}</td>
                  <td className="py-1.5 text-right font-mono">{stock.toLocaleString()}</td>
                  <td className="py-1.5 text-right">
                    <span className={cn(
                      'inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                      isLow ? 'bg-red-500/10 text-red-600' : 'bg-emerald-500/10 text-emerald-600',
                    )}>
                      {isLow ? 'Low' : 'OK'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}


function RecordTableWidget({ payload }: { payload: unknown }) {
  const p = payload as RecordTablePayload;
  const columns = p.columns ?? [];
  const rows = p.rows ?? [];

  function display(value: unknown): string {
    if (value == null || value === '') return '—';
    if (typeof value === 'number') {
      if (value > 9999) return value.toLocaleString('en-IN');
      return String(value);
    }
    return String(value).replace(/_/g, ' ');
  }

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {p.title ?? 'Records'}
          </p>
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            Source: {p.doctype ?? 'DMS'} · {p.total ?? rows.length} database record(s)
          </p>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-2">No records found.</p>
      ) : (
        <div className="max-h-72 overflow-auto rounded-lg border border-border/40">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-background">
              <tr className="border-b border-border/50">
                {columns.map((column) => (
                  <th key={column.key} className="px-2 py-2 text-left font-medium text-muted-foreground">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={String(row.id ?? row.name ?? i)} className="border-b border-border/30 last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className="px-2 py-2">
                      {display(row[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}



function GenericChartsWidget({ payload }: { payload: unknown }) {
  const p = payload as GenericChartsPayload;
  const charts = p.charts ?? [];

  function formatValue(value: number, chart: GenericChartSpec): string {
    const prefix = chart.prefix ?? '';
    const suffix = chart.suffix ?? '';
    const formatted = Math.abs(value) >= 100000 ? value.toLocaleString('en-IN') : String(Math.round(value));
    return `${prefix}${formatted}${suffix}`;
  }

  function MiniChart({ chart }: { chart: GenericChartSpec }) {
    const labels = chart.labels ?? [];
    const values = (chart.series ?? []).map((value) => Number(value) || 0);
    const max = Math.max(...values.map((value) => Math.abs(value)), 1);

    if (chart.type === 'line' && values.length > 1) {
      const width = 420;
      const height = 120;
      const pad = 16;
      const points = values.map((value, index) => {
        const x = pad + (index * (width - pad * 2)) / Math.max(values.length - 1, 1);
        const y = height - pad - (value / max) * (height - pad * 2);
        return `${x},${y}`;
      }).join(' ');

      return (
        <div className="rounded-lg border border-border/40 p-3">
          <div className="mb-2">
            <p className="text-xs font-semibold">{chart.title}</p>
            {chart.description && <p className="text-[10px] text-muted-foreground">{chart.description}</p>}
          </div>
          <svg viewBox={`0 0 ${width} ${height}`} className="h-36 w-full">
            <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" className="text-violet-500" />
            {values.map((value, index) => {
              const x = pad + (index * (width - pad * 2)) / Math.max(values.length - 1, 1);
              const y = height - pad - (value / max) * (height - pad * 2);
              return <circle key={index} cx={x} cy={y} r="3" className="fill-violet-500" />;
            })}
          </svg>
          <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
            <span>{labels[0]}</span>
            <span>Total: {formatValue(chart.total ?? values.reduce((a, b) => a + b, 0), chart)}</span>
            <span>{labels[labels.length - 1]}</span>
          </div>
        </div>
      );
    }

    return (
      <div className="rounded-lg border border-border/40 p-3">
        <div className="mb-3">
          <p className="text-xs font-semibold">{chart.title}</p>
          {chart.description && <p className="text-[10px] text-muted-foreground">{chart.description}</p>}
        </div>
        <div className="space-y-2">
          {values.map((value, index) => (
            <div key={index} className="grid grid-cols-[90px_1fr_70px] items-center gap-2 text-[10px]">
              <span className="truncate text-muted-foreground">{labels[index]}</span>
              <div className="h-2 rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-violet-500"
                  style={{ width: `${Math.max(3, (Math.abs(value) / max) * 100)}%` }}
                />
              </div>
              <span className="text-right font-medium">{formatValue(value, chart)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <div className="mb-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {p.title ?? 'Available charts'}
        </p>
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          Scope: {p.scope} · Last {p.month_limit} months · {charts.length} chart(s)
        </p>
      </div>

      {charts.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-2">No chartable data found.</p>
      ) : (
        <div className="grid gap-3">
          {charts.map((chart) => <MiniChart key={chart.id} chart={chart} />)}
        </div>
      )}
    </div>
  );
}


function TenantComparisonWidget({ payload }: { payload: unknown }) {
  const p = payload as TenantComparisonPayload;
  const data = (p.labels ?? []).map((label, i) => ({
    tenant: label,
    Sales: p.series?.[i] ?? 0,
  }));

  if (!data.length) return null;

  return (
    <div className="mt-3 rounded-xl border border-border/50 bg-background/60 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">Tenant Comparison</p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="tenant" tick={{ fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`} width={44} />
          <Tooltip
            formatter={(v: number) => [`₹${v.toLocaleString()}`, 'Sales']}
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
          />
          <Bar dataKey="Sales" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Filter chips ─────────────────────────────────────────────────────────────
function FilterChips({ filters }: { filters: FiltersApplied }) {
  const chips: { label: string; value: string }[] = [];
  if (filters.metric) chips.push({ label: 'Metric', value: filters.metric });
  if (filters.time_range) chips.push({ label: 'Period', value: filters.time_range });
  if (filters.tenant_id && filters.tenant_id !== 'all_allowed_tenants') {
    chips.push({ label: 'Tenant', value: filters.tenant_id });
  }
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2 mb-1">
      {chips.map((chip) => (
        <span key={chip.label} className="inline-flex items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-[10px] text-violet-600 border border-violet-500/20">
          <span className="text-violet-400/80">{chip.label}:</span>
          {chip.value}
        </span>
      ))}
    </div>
  );
}

// ─── Inline widget renderer ───────────────────────────────────────────────────
function InlineWidgets({ agentData }: { agentData: AgentResponse }) {
  return (
    <>
      {agentData.widgets_to_show.map((widgetId) => {
        const payload = agentData.widget_payloads[widgetId];
        if (widgetId === 'sales_chart') return <SalesChartWidget key={widgetId} payload={payload} />;
        if (widgetId === 'service_count_chart') return <ServiceCountWidget key={widgetId} payload={payload} />;
        if (widgetId === 'inventory_table') return <InventoryTableWidget key={widgetId} payload={payload} />;
        if (widgetId === 'tenant_comparison_chart') return <TenantComparisonWidget key={widgetId} payload={payload} />;
        if (widgetId === 'record_table') return <RecordTableWidget key={widgetId} payload={payload} />;
        if (widgetId === 'generic_charts') return <GenericChartsWidget key={widgetId} payload={payload} />;
        return null;
      })}
    </>
  );
}

// ─── Markdown-lite renderer ───────────────────────────────────────────────────
function MessageContent({ text }: { text: string }) {
  const lines = text.split('\n');
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith('**') && line.endsWith('**') && !line.slice(2, -2).includes('**')) {
          return <p key={i} className="font-semibold">{line.slice(2, -2)}</p>;
        }
        if (line.startsWith('- ')) {
          return (
            <div key={i} className="flex gap-2 items-start">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-current shrink-0 opacity-60" />
              <span dangerouslySetInnerHTML={{ __html: line.slice(2).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
            </div>
          );
        }
        if (line.startsWith('| ') && line.includes(' | ')) {
          const cells = line.split('|').filter(c => c.trim());
          if (cells[0].trim().startsWith('---')) return null;
          return (
            <div key={i} className="flex gap-0 text-xs font-mono">
              {cells.map((c, j) => (
                <span key={j} className="border border-border/40 px-2 py-1 min-w-[80px]"
                  dangerouslySetInnerHTML={{ __html: c.trim().replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
              ))}
            </div>
          );
        }
        if (line === '---') return <hr key={i} className="border-border/50 my-2" />;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return (
          <p key={i} dangerouslySetInnerHTML={{ __html: line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
        );
      })}
    </div>
  );
}


function normalizeRpaPhone(value: string): string {
  return value.replace(/\D/g, '').slice(-10);
}

function defaultRpaForm(): RpaContactPayload {
  return {
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    vehicle_interest: '',
    source: 'DMS Dashboard RPA',
    notes: '',
  };
}

function RpaAgentPanel({ user }: { user: User | null }) {
  const [form, setForm] = useState<RpaContactPayload>(() => defaultRpaForm());
  const [target, setTarget] = useState<RpaSaveTarget>('both');
  const [progress, setProgress] = useState<RpaProgressState>({
    phase: 'idle',
    percent: 0,
    label: 'Ready',
    detail: 'Enter contact details and choose where to save the record.',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<RpaSaveResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contactsRefreshKey, setContactsRefreshKey] = useState(0);

  const role = resolveRole(user);
  const company = resolveCompany(user);
  const needsGhl = target === 'ghl' || target === 'both';
  const isGroupAdmin = user?.role === 'group_admin' || user?.company === 'Group';

  function updateField(field: keyof RpaContactPayload, value: string) {
    setForm((prev) => ({
      ...prev,
      [field]: field === 'phone' ? normalizeRpaPhone(value) : value,
    }));
  }

  function validateForm(): string | null {
    if (!isGroupAdmin) return 'GoHighLevel RPA is available only for the full admin account.';
    if (!form.first_name?.trim()) return 'First name is required.';
    if (!form.email?.trim() && !form.phone?.trim()) return 'Add at least an email or a 10-digit phone number.';
    if (form.phone && !/^\d{10}$/.test(form.phone)) return 'Phone must be exactly 10 digits without country code or plus sign.';
    return null;
  }

  function setStage(phase: RpaPhase, percent: number, label: string, detail: string) {
    setProgress({ phase, percent, label, detail });
  }

  async function submitRpa() {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      setProgress({ phase: 'error', percent: 0, label: 'Input issue', detail: validationError });
      return;
    }

    setIsSubmitting(true);
    setResult(null);
    setError(null);

    try {
      setStage('validating', 8, 'Preparing contact', 'Validating form details and save target.');

      if (needsGhl) {
        setStage('session', 18, 'Checking GHL session', 'Looking for an existing saved GoHighLevel browser session.');
        const session = await checkGhlSession({ role, company, deepCheck: false });

        if (!session.storage_state_exists) {
          setStage(
            'login',
            30,
            'Waiting for GoHighLevel login',
            'A browser login window should open. Complete login and security verification there.',
          );
          await openGhlLogin({ role, company, timeoutSeconds: 600 });
        }

        setStage('syncing', 55, 'Starting hidden CRM sync', 'After login, the backend runs the GHL contact creation in a hidden browser session.');
      } else {
        setStage('saving', 45, 'Saving to DMS', 'Creating the contact in the local DMS backend.');
      }

      setStage(needsGhl ? 'syncing' : 'saving', needsGhl ? 72 : 70, needsGhl ? 'Syncing with GHL CRM' : 'Saving locally', needsGhl ? 'Creating the GHL contact, assigning tag, and verifying the result.' : 'Creating the local DMS CRM Contact.');

      const saved = await saveRpaContact({
        role,
        company,
        target,
        contact: {
          ...form,
          first_name: form.first_name.trim(),
          last_name: form.last_name?.trim() ?? '',
          email: form.email?.trim() ?? '',
          phone: normalizeRpaPhone(form.phone ?? ''),
          vehicle_interest: form.vehicle_interest?.trim() ?? '',
          source: form.source?.trim() || 'DMS Dashboard RPA',
          notes: form.notes?.trim() ?? '',
        },
      });

      if (needsGhl && saved.status !== 'Success') {
        throw new Error(saved.message || 'GHL CRM sync did not complete successfully.');
      }

      if (!needsGhl && saved.status !== 'Success') {
        throw new Error(saved.message || 'DMS save did not complete successfully.');
      }

      setResult(saved);
      setContactsRefreshKey((key) => key + 1);
      setStage(
        'success',
        100,
        target === 'dms' ? 'Saved to DMS' : target === 'ghl' ? 'Saved to GHL CRM' : 'Saved to DMS and GHL CRM',
        'Contact is ready. Backend returned final success confirmation.',
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'RPA operation failed.';
      setError(message);
      setStage('error', 100, 'Operation failed', message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function resetForm() {
    setForm(defaultRpaForm());
    setTarget('both');
    setResult(null);
    setError(null);
    setProgress({
      phase: 'idle',
      percent: 0,
      label: 'Ready',
      detail: 'Enter contact details and choose where to save the record.',
    });
  }

  const progressTone =
    progress.phase === 'success'
      ? 'bg-emerald-500'
      : progress.phase === 'error'
        ? 'bg-red-500'
        : 'bg-violet-500';

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="border-b border-border bg-card/50 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-violet-500">
              <Workflow className="h-3.5 w-3.5" />
              RPA Agent
            </div>
            <h1 className="text-xl font-semibold text-foreground">GoHighLevel Contact Automation</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Admin-only workflow to save contacts in DMS, GoHighLevel CRM, or both.
            </p>
          </div>
          <div className="hidden rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-600 md:block">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              Backend-guarded admin access
            </div>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="mx-auto grid max-w-5xl gap-5 p-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-foreground">Contact details</h2>
                <p className="text-xs text-muted-foreground">Phone is sent as plain 10 digits. No plus sign or country code.</p>
              </div>
              <button
                type="button"
                onClick={resetForm}
                disabled={isSubmitting}
                className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                Reset
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">First name *</span>
                <input
                  value={form.first_name}
                  onChange={(e) => updateField('first_name', e.target.value)}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="Arjun"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">Last name</span>
                <input
                  value={form.last_name ?? ''}
                  onChange={(e) => updateField('last_name', e.target.value)}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="Pillai"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">Email</span>
                <input
                  value={form.email ?? ''}
                  onChange={(e) => updateField('email', e.target.value)}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="arjun@example.com"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">Phone</span>
                <input
                  value={form.phone ?? ''}
                  onChange={(e) => updateField('phone', e.target.value)}
                  disabled={isSubmitting}
                  inputMode="numeric"
                  maxLength={10}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="9876543210"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">Vehicle interest</span>
                <input
                  value={form.vehicle_interest ?? ''}
                  onChange={(e) => updateField('vehicle_interest', e.target.value)}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="Honda City"
                />
              </label>

              <label className="space-y-1.5">
                <span className="text-xs font-medium text-foreground">Source</span>
                <input
                  value={form.source ?? ''}
                  onChange={(e) => updateField('source', e.target.value)}
                  disabled={isSubmitting}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="DMS Dashboard RPA"
                />
              </label>

              <label className="space-y-1.5 md:col-span-2">
                <span className="text-xs font-medium text-foreground">Notes</span>
                <textarea
                  value={form.notes ?? ''}
                  onChange={(e) => updateField('notes', e.target.value)}
                  disabled={isSubmitting}
                  rows={4}
                  className="w-full resize-none rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-violet-500 disabled:opacity-60"
                  placeholder="Lead source, requirement, or follow-up notes"
                />
              </label>
            </div>

            <div className="mt-6">
              <p className="mb-2 text-xs font-medium text-foreground">Save target</p>
              <div className="grid gap-3 md:grid-cols-3">
                {RPA_TARGETS.map((option) => {
                  const Icon = option.icon;
                  const active = target === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTarget(option.value)}
                      disabled={isSubmitting}
                      className={cn(
                        'rounded-xl border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60',
                        active
                          ? 'border-violet-500 bg-violet-500/10 shadow-sm'
                          : 'border-border bg-background hover:bg-accent',
                      )}
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <Icon className={cn('h-4 w-4', active ? 'text-violet-500' : 'text-muted-foreground')} />
                        <span className="text-sm font-semibold">{option.label}</span>
                      </div>
                      <p className="text-[11px] leading-relaxed text-muted-foreground">{option.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-muted-foreground">
                GHL login appears only when no saved session exists. After login, sync runs hidden in the backend.
              </p>
              <button
                type="button"
                onClick={submitRpa}
                disabled={isSubmitting}
                className={cn(
                  'inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition',
                  isSubmitting
                    ? 'cursor-not-allowed bg-violet-500/70'
                    : 'bg-gradient-to-br from-violet-500 to-indigo-600 shadow-md shadow-violet-500/25 hover:shadow-lg',
                )}
              >
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Workflow className="h-4 w-4" />}
                {isSubmitting ? 'Processing...' : 'Run RPA Save'}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-foreground">Progress</h2>
                  <p className="text-xs text-muted-foreground">100% is shown only after backend final success.</p>
                </div>
                <div className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-xl',
                  progress.phase === 'success'
                    ? 'bg-emerald-500/10 text-emerald-500'
                    : progress.phase === 'error'
                      ? 'bg-red-500/10 text-red-500'
                      : 'bg-violet-500/10 text-violet-500',
                )}>
                  {progress.phase === 'success'
                    ? <CheckCircle2 className="h-5 w-5" />
                    : progress.phase === 'error'
                      ? <AlertCircle className="h-5 w-5" />
                      : isSubmitting
                        ? <Loader2 className="h-5 w-5 animate-spin" />
                        : <Workflow className="h-5 w-5" />}
                </div>
              </div>

              <div className="mb-3 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn('h-full rounded-full transition-all duration-700', progressTone)}
                  style={{ width: `${progress.percent}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground">{progress.label}</span>
                <span className="font-mono text-muted-foreground">{progress.percent}%</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{progress.detail}</p>

              {isSubmitting && (
                <div className="mt-4 rounded-xl border border-violet-500/20 bg-violet-500/10 p-3 text-xs text-violet-600">
                  Sync is running in the backend. You can keep this dashboard open; do not interact with the backend browser window.
                </div>
              )}

              {error && (
                <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-600">
                  {error}
                </div>
              )}
            </div>

            {result && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2 text-emerald-600">
                  <CheckCircle2 className="h-5 w-5" />
                  <h2 className="text-sm font-semibold">Save completed</h2>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between gap-3">
                    <span className="text-muted-foreground">Status</span>
                    <span className="font-semibold text-foreground">{result.status}</span>
                  </div>
                  {result.dms_contact && (
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">DMS Contact</span>
                      <span className="font-mono text-foreground">{result.dms_contact}</span>
                    </div>
                  )}
                  {result.rpa_job && (
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">RPA Job</span>
                      <span className="font-mono text-foreground">{result.rpa_job}</span>
                    </div>
                  )}
                  <div className="pt-2 text-muted-foreground">{result.message}</div>
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-border bg-card p-5 text-xs text-muted-foreground">
              <h3 className="mb-2 text-sm font-semibold text-foreground">Execution notes</h3>
              <ul className="space-y-2">
                <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 rounded-full bg-violet-500" /> Tenant users cannot access this module.</li>
                <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 rounded-full bg-violet-500" /> GHL sync uses the backend session and verified tag assignment.</li>
                <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 rounded-full bg-violet-500" /> Phone is normalized to 10 digits before sending to RPA.</li>
              </ul>
            </div>
          </div>

          <div className="lg:col-span-2">
            <RpaSavedContactsTable role={role} company={company} refreshSignal={contactsRefreshKey} />
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}


// ─── Main page ────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const { user } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeModule, setActiveModule] = useState<WorkspaceModule>('chat');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  function startNewChat() {
    setActiveModule('chat');
    setMessages([]);
    setInput('');
  }

  async function sendMessage(text: string) {
    if (!text.trim() || isTyping) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';


    setIsTyping(true);
    try {
      const conversationContext = messages
        .slice(-6)
        .map((message) => `${message.role}: ${message.content}`)
        .join('\n');

      const data = await queryDashboardAgent({
        query: text.trim(),
        role: resolveRole(user),
        company: resolveCompany(user),
        conversationContext,
      });
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.text_response,
          timestamp: new Date(),
          agentData: data,
        },
      ]);
    } catch {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Unable to reach the DMS backend AI agent. Please make sure the DMS backend is running and the AI endpoint is available.',
          timestamp: new Date(),
          error: true,
        },
      ]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }


  const initials = user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2) ?? 'U';
  const isRpaAdmin = user?.role === 'group_admin' || user?.company === 'Group';

  return (
    <div className="flex h-full -m-6 overflow-hidden">

      {/* ── Left: Agent Module Sidebar ───────────────────────────────────────── */}
      <div className="flex w-64 shrink-0 flex-col bg-[#0f0f0f] text-white">
        <div className="flex items-center gap-2 px-3 pt-4 pb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm font-semibold">DMS AI</span>
        </div>

        <div className="px-3 pb-3">
          <button
            onClick={startNewChat}
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white/80 hover:bg-white/10 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>
        </div>

        <div className="px-3 pb-3">
          <div className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-white/30">
            Agents
          </div>
          <div className="grid gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveModule('chat');
                startNewChat();
              }}
              className={cn(
                'flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition-colors',
                activeModule === 'chat'
                  ? 'border-violet-400/60 bg-violet-500/20 text-white'
                  : 'border-white/10 bg-white/5 text-white/80 hover:bg-white/10',
              )}
            >
              <span className="flex items-center gap-2">
                <Bot className="h-4 w-4" />
                Main Chat Agent
              </span>
              <span className="text-[10px] text-white/40">DMS</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveModule('voice')}
              className={cn(
                'flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition-colors',
                activeModule === 'voice'
                  ? 'border-violet-400/60 bg-violet-500/20 text-white'
                  : 'border-white/10 bg-white/5 text-white/80 hover:bg-white/10',
              )}
            >
              <span className="flex items-center gap-2">
                <PhoneCall className="h-4 w-4" />
                Voice Agent
              </span>
              <span className="text-[10px] text-white/40">Soon</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveModule('rpa')}
              className={cn(
                'flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition-colors',
                activeModule === 'rpa'
                  ? 'border-violet-400/60 bg-violet-500/20 text-white'
                  : 'border-white/10 bg-white/5 text-white/80 hover:bg-white/10',
              )}
            >
              <span className="flex items-center gap-2">
                <Workflow className="h-4 w-4" />
                RPA Agent
              </span>
              <span className="text-[10px] text-white/40">GHL</span>
            </button>
          </div>
        </div>

        <div className="mt-auto border-t border-white/[0.06] p-3">
          <div className="flex items-center gap-2 rounded-lg px-2 py-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-[11px] font-bold text-white">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-white/80">{user?.full_name ?? 'User'}</p>
              <p className="truncate text-[10px] text-white/40">{user?.role?.replace(/_/g, ' ')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right: Chat Area ─────────────────────────────────────────────────── */}
      <div className="relative flex flex-1 flex-col bg-background overflow-hidden">
        {activeModule === 'voice' && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-background">
            <div className="max-w-sm rounded-2xl border border-border bg-card p-6 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <PhoneCall className="h-5 w-5" />
              </div>
              <h2 className="text-base font-semibold text-foreground">Voice Agent</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Voice automation is not enabled yet. Use Main Chat Agent or RPA Agent for now.
              </p>
            </div>
          </div>
        )}

        {activeModule === 'rpa' && !isRpaAdmin && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-background">
            <div className="max-w-sm rounded-2xl border border-border bg-card p-6 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-red-500/10 text-red-500">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h2 className="text-base font-semibold text-foreground">RPA Agent is admin-only</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                GoHighLevel RPA is available only for the full admin account.
              </p>
            </div>
          </div>
        )}

        {activeModule === 'rpa' && isRpaAdmin && (
          <div className="absolute inset-0 z-20 bg-background">
            <RpaAgentPanel user={user} />
          </div>
        )}

        {messages.length === 0 && !isTyping ? (
          /* Welcome / Empty state */
          <div className="flex flex-1 flex-col items-center justify-center p-8 overflow-y-auto">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/25 mb-5">
              <Sparkles className="h-8 w-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-1">DMS AI Assistant</h2>
            <p className="text-sm text-muted-foreground mb-8 text-center max-w-sm">
              Ask about sales, service records, inventory, or compare performance across tenants.
            </p>

            <div className="grid grid-cols-2 gap-3 w-full max-w-xl">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt.label}
                  onClick={() => sendMessage(prompt.label)}
                  className="group flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left hover:bg-accent hover:border-primary/20 transition-all"
                >
                  <prompt.icon className={cn('h-5 w-5 mt-0.5 shrink-0', prompt.color)} />
                  <span className="text-sm text-foreground/80 group-hover:text-foreground transition-colors leading-snug">
                    {prompt.label}
                  </span>
                </button>
              ))}
            </div>

            <div className="mt-8 flex items-center gap-6 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Real-time data</span>
              <span className="flex items-center gap-1.5"><Star className="h-3.5 w-3.5" /> Context-aware</span>
              <span className="flex items-center gap-1.5"><Bot className="h-3.5 w-3.5" /> DMS-trained</span>
            </div>
          </div>
        ) : (
          /* Message thread */
          <ScrollArea className="flex-1 px-4 py-6">
            <div className="mx-auto max-w-2xl space-y-6">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} userInitials={initials} />
              ))}

              {isTyping && (
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                  <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
                    <TypingDots />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>
        )}

        {/* Input area */}
        <div className="border-t border-border bg-background/80 backdrop-blur-sm px-4 py-4">
          <div className="mx-auto max-w-2xl">
            <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-card shadow-sm focus-within:border-primary/50 focus-within:shadow-md transition-all">
              <button className="absolute left-3 bottom-3 text-muted-foreground hover:text-foreground transition-colors">
                <Paperclip className="h-4 w-4" />
              </button>

              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={(e) => { setInput(e.target.value); autoResize(); }}
                onKeyDown={handleKeyDown}
                placeholder="Ask about sales, inventory, service records..."
                className="flex-1 resize-none bg-transparent pl-10 pr-24 py-3.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none max-h-40 min-h-[52px]"
              />

              <div className="absolute right-3 bottom-2.5 flex items-center gap-1.5">
                <button className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                  <Mic className="h-4 w-4" />
                </button>
                <button
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim() || isTyping}
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-xl transition-all',
                    input.trim() && !isTyping
                      ? 'bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-md shadow-violet-500/30 hover:shadow-lg hover:scale-105'
                      : 'bg-muted text-muted-foreground cursor-not-allowed',
                  )}
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>

            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              DMS AI can make mistakes. Verify important information before acting on it.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function ChatMessage({ message, userInitials }: { message: Message; userInitials: string }) {
  const isUser = message.role === 'user';
  const [liked, setLiked] = useState<boolean | null>(null);
  const [copied, setCopied] = useState(false);

  function copyText() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="flex items-end gap-2 max-w-[75%]">
          <div className="flex flex-col items-end gap-1">
            <div className="rounded-2xl rounded-br-sm bg-gradient-to-br from-violet-500 to-indigo-600 px-4 py-3 text-white shadow-md shadow-violet-500/20">
              <p className="text-sm leading-relaxed">{message.content}</p>
            </div>
            <span className="text-[10px] text-muted-foreground pr-1">{formatTime(message.timestamp)}</span>
          </div>
          <Avatar className="h-8 w-8 shrink-0 mb-5">
            <AvatarFallback className="bg-indigo-600 text-white text-xs font-semibold">{userInitials}</AvatarFallback>
          </Avatar>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 group">
      <div className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full shadow-md',
        message.error
          ? 'bg-red-500/20'
          : 'bg-gradient-to-br from-violet-500 to-indigo-600 shadow-violet-500/20',
      )}>
        {message.error
          ? <AlertCircle className="h-4 w-4 text-red-500" />
          : <Sparkles className="h-4 w-4 text-white" />}
      </div>
      <div className="flex flex-col gap-1 min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-foreground">DMS AI</span>
          <span className="text-[10px] text-muted-foreground">{formatTime(message.timestamp)}</span>
          {message.agentData?.intent && !message.error && (
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground uppercase tracking-wide">
              {message.agentData.intent.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        <div className={cn(
          'rounded-2xl rounded-tl-sm px-4 py-3',
          message.error
            ? 'bg-red-500/5 border border-red-500/20'
            : 'bg-muted/60 border border-border/50',
        )}>
          <MessageContent text={message.content} />

          {/* Filter chips + widgets from agent response */}
          {message.agentData && !message.error && (
            <>
              <FilterChips filters={message.agentData.filters_applied} />
              <InlineWidgets agentData={message.agentData} />
            </>
          )}
        </div>

        {/* Action row */}
        <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={copyText}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <Copy className="h-3 w-3" />
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors">
            <RotateCcw className="h-3 w-3" />
            Regenerate
          </button>
          <div className="ml-auto flex items-center gap-1">
            <button
              onClick={() => setLiked(true)}
              className={cn('rounded-lg p-1 transition-colors', liked === true ? 'text-emerald-500' : 'text-muted-foreground hover:text-foreground hover:bg-accent')}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setLiked(false)}
              className={cn('rounded-lg p-1 transition-colors', liked === false ? 'text-red-500' : 'text-muted-foreground hover:text-foreground hover:bg-accent')}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
        />
      ))}
    </div>
  );
}
