'use client';
import { useState, useRef, useEffect } from 'react';
import {
  Send, Plus, Search, Bot, Sparkles, Car, TrendingUp,
  Users, ChevronDown, MoreHorizontal, Edit3,
  Paperclip, Mic, RotateCcw, ThumbsUp, ThumbsDown, Copy,
  MessageSquare, Clock, Star, AlertCircle,
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
import { queryDashboardAgent, type AgentResponse, type FiltersApplied } from '@/services/api/aiAgent';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agentData?: AgentResponse;
  error?: boolean;
}

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  isPinned?: boolean;
}

// ─── Mock history ─────────────────────────────────────────────────────────────
const MOCK_HISTORY: Conversation[] = [
  { id: 'c1', title: 'Honda Civic lead follow-up', lastMessage: 'I can help you draft...', timestamp: new Date(Date.now() - 1000 * 60 * 20), isPinned: true },
  { id: 'c2', title: 'Monthly sales report summary', lastMessage: 'Here is the breakdown...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2) },
  { id: 'c3', title: 'Test drive scheduling tips', lastMessage: 'Best practices include...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5) },
  { id: 'c4', title: 'Customer objection handling', lastMessage: 'When a customer says...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24) },
  { id: 'c5', title: 'NEXA vs Honda comparison', lastMessage: 'The key differences...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 25) },
  { id: 'c6', title: 'EMI calculation for City S', lastMessage: 'For a ₹12L vehicle...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48) },
  { id: 'c7', title: 'Follow-up email template', lastMessage: 'Subject: Your test drive...', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 72) },
];

const SUGGESTED_PROMPTS = [
  { icon: TrendingUp, label: "What was the sales in the last 5 months?", color: 'text-emerald-500' },
  { icon: Users, label: "Show me service records for the last 3 months", color: 'text-blue-500' },
  { icon: Car, label: "What is the current inventory stock?", color: 'text-orange-500' },
  { icon: MessageSquare, label: "Compare sales across all tenants", color: 'text-purple-500' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatGroupLabel(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  if (diff < 1000 * 60 * 60 * 24) return 'Today';
  if (diff < 1000 * 60 * 60 * 48) return 'Yesterday';
  return 'Previous 7 days';
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

// ─── Main page ────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const { user } = useAuthStore();
  const [conversations, setConversations] = useState<Conversation[]>(MOCK_HISTORY);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
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
    setActiveId(null);
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

    if (!activeId) {
      const newId = `c-${Date.now()}`;
      setConversations((prev) => [
        {
          id: newId,
          title: text.trim().slice(0, 40) + (text.length > 40 ? '...' : ''),
          lastMessage: '',
          timestamp: new Date(),
        },
        ...prev,
      ]);
      setActiveId(newId);
    }

    setIsTyping(true);
    try {
      const data = await queryDashboardAgent({
        query: text.trim(),
        role: resolveRole(user),
        company: resolveCompany(user),
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

  const filteredConversations = conversations.filter(
    (c) => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase()),
  );
  const pinned = filteredConversations.filter((c) => c.isPinned);
  const unpinned = filteredConversations.filter((c) => !c.isPinned);
  const groups = [
    { label: 'Today', items: unpinned.filter((c) => formatGroupLabel(c.timestamp) === 'Today') },
    { label: 'Yesterday', items: unpinned.filter((c) => formatGroupLabel(c.timestamp) === 'Yesterday') },
    { label: 'Previous 7 days', items: unpinned.filter((c) => formatGroupLabel(c.timestamp) === 'Previous 7 days') },
  ].filter((g) => g.items.length > 0);

  const initials = user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2) ?? 'U';

  return (
    <div className="flex h-full -m-6 overflow-hidden">

      {/* ── Left: Chat History Sidebar ──────────────────────────────────────── */}
      <div className="flex w-64 shrink-0 flex-col bg-[#0f0f0f] text-white">
        {/* Header */}
        <div className="flex items-center justify-between px-3 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <span className="text-sm font-semibold">DMS AI</span>
          </div>
          <button
            onClick={startNewChat}
            className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-white/10 transition-colors"
            title="New Chat"
          >
            <Edit3 className="h-4 w-4 text-white/70" />
          </button>
        </div>

        {/* New Chat button */}
        <div className="px-3 pb-3">
          <button
            onClick={startNewChat}
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white/80 hover:bg-white/10 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/30" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg bg-white/5 pl-8 pr-3 py-2 text-xs text-white/70 placeholder:text-white/30 border border-white/5 focus:outline-none focus:border-white/20 transition-colors"
            />
          </div>
        </div>

        {/* History list */}
        <ScrollArea className="flex-1 px-2">
          {pinned.length > 0 && (
            <div className="mb-2">
              <div className="flex items-center gap-1.5 px-2 py-1">
                <Star className="h-3 w-3 text-white/30" />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-white/30">Pinned</span>
              </div>
              {pinned.map((conv) => (
                <ConvItem
                  key={conv.id}
                  conv={conv}
                  isActive={activeId === conv.id}
                  isHovered={hoveredId === conv.id}
                  onSelect={() => { setActiveId(conv.id); setMessages([]); }}
                  onHover={setHoveredId}
                />
              ))}
              <div className="mx-2 my-2 border-t border-white/[0.06]" />
            </div>
          )}

          {groups.map((group) => (
            <div key={group.label} className="mb-1">
              <div className="px-2 py-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-white/30">{group.label}</span>
              </div>
              {group.items.map((conv) => (
                <ConvItem
                  key={conv.id}
                  conv={conv}
                  isActive={activeId === conv.id}
                  isHovered={hoveredId === conv.id}
                  onSelect={() => { setActiveId(conv.id); setMessages([]); }}
                  onHover={setHoveredId}
                />
              ))}
            </div>
          ))}

          {filteredConversations.length === 0 && (
            <div className="py-8 text-center text-xs text-white/30">No conversations found</div>
          )}
        </ScrollArea>

        {/* Footer */}
        <div className="border-t border-white/[0.06] p-3">
          <div className="flex items-center gap-2 rounded-lg px-2 py-2 hover:bg-white/5 cursor-pointer transition-colors">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-[11px] font-bold text-white shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-white/80">{user?.full_name ?? 'User'}</p>
              <p className="truncate text-[10px] text-white/40">{user?.role?.replace(/_/g, ' ')}</p>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-white/30 shrink-0" />
          </div>
        </div>
      </div>

      {/* ── Right: Chat Area ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col bg-background overflow-hidden">

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
function ConvItem({
  conv, isActive, isHovered, onSelect, onHover,
}: {
  conv: Conversation;
  isActive: boolean;
  isHovered: boolean;
  onSelect: () => void;
  onHover: (id: string | null) => void;
}) {
  return (
    <div
      className={cn(
        'group relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors',
        isActive ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white/80',
      )}
      onClick={onSelect}
      onMouseEnter={() => onHover(conv.id)}
      onMouseLeave={() => onHover(null)}
    >
      <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
      <span className="flex-1 truncate text-xs">{conv.title}</span>
      {(isActive || isHovered) && (
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            className="flex h-5 w-5 items-center justify-center rounded hover:bg-white/10 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

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
