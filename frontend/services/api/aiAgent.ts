import { csrfStorage } from './client';

// Vividity follows the same-origin proxy in Railway production. Local
// development continues to provide the direct backend URL via .env.local.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

export interface FiltersApplied {
  metric?: string | null;
  time_range?: string | null;
  tenant_id?: string | null;
  other?: Record<string, unknown> | null;
}

export interface AnalyticalDimension {
  key: string;
  label: string;
  type: 'category' | 'date' | 'datetime' | 'text';
}

export interface AnalyticalMeasure {
  key: string;
  label: string;
  format: 'integer' | 'decimal' | 'currency' | 'percentage';
  currency?: string;
}

export interface AnalyticalDataset {
  schema_version: number;
  resource: string;
  title: string;
  dimensions: AnalyticalDimension[];
  measures: AnalyticalMeasure[];
  rows: Array<Record<string, string | number | boolean | null>>;
  totals: Record<string, number | null>;
  filters: Record<string, unknown>;
  row_count: number;
}

export interface AnalyticalViewSpec {
  type: 'table' | 'bar' | 'line' | 'pie' | 'area' | 'stacked_bar';
  x_field?: string | null;
  series_field?: string | null;
  value_field?: string | null;
  title: string;
}

export interface AnalyticalViewPayload {
  snapshot_id: string;
  source_hash: string;
  title: string;
  resource: string;
  dataset: AnalyticalDataset;
  view: AnalyticalViewSpec;
  reused: boolean;
  data_source: string;
}

export interface AgentResponse {
  intent: string;
  filters_applied: FiltersApplied;
  widgets_to_show: string[];
  widgets_to_hide: string[];
  text_response: string;
  widget_payloads: Record<string, unknown>;
  conversation_id?: string;
  conversation_title?: string;
  memory_summary?: string;
  active_snapshot_id?: string;
  snapshot_source_hash?: string;
}

export interface AgentConversationSummary {
  id: string;
  title: string;
  company_name?: string | null;
  is_group_admin: boolean;
  message_count: number;
  memory_summary?: string;
  last_intent?: string;
  last_resource?: string;
  last_message_at?: string;
  created_at?: string;
  updated_at?: string;
  status: string;
}

export interface AgentConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sequence_no: number;
  intent?: string;
  agent_data?: AgentResponse | null;
  error?: boolean;
}

export interface AgentConversationDetail {
  conversation: AgentConversationSummary;
  messages: AgentConversationMessage[];
}

export function resolveAgentHeaders(
  _role: string,
  _company: string,
  _clientUserId?: string,
): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  const csrfToken = csrfStorage.get();
  if (csrfToken) headers['X-Frappe-CSRF-Token'] = csrfToken;
  return headers;
}

type FrappeEnvelope<T> = {
  message?: {
    success?: boolean;
    data?: T;
    message?: string;
  } | string;
  success?: boolean;
  data?: T;
};

function unwrapFrappe<T>(raw: unknown): T {
  const value = raw as FrappeEnvelope<T>;
  const nestedMessage =
    typeof value.message === 'object' && value.message !== null
      ? value.message
      : undefined;
  const rootMessage = typeof value.message === 'string' ? value.message : undefined;
  if (nestedMessage?.success === false) {
    throw new Error(nestedMessage.message || 'AI request failed');
  }
  if (value.success === false) {
    throw new Error(rootMessage || 'AI request failed');
  }
  return (nestedMessage?.data ?? value.data ?? raw) as T;
}

async function frappeRequest<T>(opts: {
  path: string;
  method?: 'GET' | 'POST';
  role: string;
  company: string;
  clientUserId?: string;
  body?: Record<string, unknown>;
}): Promise<T> {
  const method = opts.method ?? 'POST';
  const response = await fetch(`${API_BASE}/api/method/${opts.path}`, {
    method,
    headers: resolveAgentHeaders(opts.role, opts.company, opts.clientUserId),
    credentials: 'include',
    body: method === 'GET' ? undefined : JSON.stringify(opts.body ?? {}),
  });
  const raw = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      typeof raw?.message === 'string'
        ? raw.message
        : `DMS API error ${response.status}`,
    );
  }
  return unwrapFrappe<T>(raw);
}

export async function queryDashboardAgent(opts: {
  query: string;
  role: string;
  company: string;
  clientUserId?: string;
  conversationId?: string | null;
}): Promise<AgentResponse> {
  return frappeRequest<AgentResponse>({
    path: 'dms.api.ai_agent.query',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
    body: {
      query: opts.query,
      conversation_id: opts.conversationId ?? '',
    },
  });
}

export async function listAgentConversations(opts: {
  role: string;
  company: string;
  clientUserId?: string;
}): Promise<AgentConversationSummary[]> {
  return frappeRequest<AgentConversationSummary[]>({
    path: 'dms.api.ai_agent.list_conversations',
    method: 'GET',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
  });
}

export async function getAgentConversation(opts: {
  conversationId: string;
  role: string;
  company: string;
  clientUserId?: string;
}): Promise<AgentConversationDetail> {
  return frappeRequest<AgentConversationDetail>({
    path: 'dms.api.ai_agent.get_conversation',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
    body: { conversation_id: opts.conversationId },
  });
}
