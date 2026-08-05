import { tokenStorage } from './client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://dms.localhost:8000';

function isMockToken(token: string | null): boolean {
  return Boolean(token && token.endsWith('.mock_sig'));
}

export interface FiltersApplied {
  metric?: string | null;
  time_range?: string | null;
  tenant_id?: string | null;
  other?: Record<string, unknown> | null;
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

const ROLE_MAP: Record<string, string> = {
  group_admin: 'service_centre_admin',
};

// Keep current frontend compatibility.
// Backend accepts these aliases and resolves them to Honda/NEXA/Jaguar.
const TENANT_MAP: Record<string, string> = {
  Honda: 'toyota',
  NEXA: 'suzuki',
  Jaguar: 'hyundai',
};

export function resolveAgentHeaders(
  role: string,
  company: string,
  clientUserId?: string,
): Record<string, string> {
  const xUserRole = ROLE_MAP[role] ?? 'tenant_user';

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'x-user-role': xUserRole,
  };

  if (xUserRole === 'tenant_user') {
    headers['x-tenant-id'] = TENANT_MAP[company] ?? company.toLowerCase();
  }

  if (clientUserId) {
    headers['x-client-user-id'] = clientUserId;
  }

  const token = tokenStorage.getAccess();

  // Demo mock JWTs are only for the Next.js frontend middleware.
  // Do not send them to Frappe because Frappe will reject the fake signature.
  if (token && !isMockToken(token)) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

type FrappeAgentEnvelope = {
  message?: {
    success?: boolean;
    data?: AgentResponse;
    message?: string;
  } | string;
  success?: boolean;
  data?: AgentResponse;
};

function unwrapFrappeResponse(raw: unknown): AgentResponse {
  const value = raw as FrappeAgentEnvelope;
  const nestedMessage =
    typeof value.message === 'object' && value.message !== null
      ? value.message
      : undefined;
  const rootMessage = typeof value.message === 'string' ? value.message : undefined;

  if (nestedMessage?.success === false) {
    throw new Error(nestedMessage.message || 'AI agent request failed');
  }

  if (value.success === false) {
    throw new Error(rootMessage || 'AI agent request failed');
  }

  const data = nestedMessage?.data ?? value.data ?? raw;

  return data as AgentResponse;
}

export async function queryDashboardAgent(opts: {
  query: string;
  role: string;
  company: string;
  clientUserId?: string;
  conversationId?: string | null;
}): Promise<AgentResponse> {
  const headers = resolveAgentHeaders(
    opts.role,
    opts.company,
    opts.clientUserId,
  );

  const res = await fetch(`${API_BASE}/api/method/dms.api.ai_agent.query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      query: opts.query,
      conversation_id: opts.conversationId ?? '',
    }),
  });

  const raw = await res.json().catch(() => null);

  if (!res.ok) {
    throw new Error(
      typeof raw?.message === 'string'
        ? raw.message
        : `AI agent error ${res.status}`,
    );
  }

  return unwrapFrappeResponse(raw);
}

type FrappeDataEnvelope<T> = {
  message?: {
    success?: boolean;
    data?: T;
    message?: string;
  } | string;
  success?: boolean;
  data?: T;
};

function unwrapFrappeData<T>(raw: unknown): T {
  const value = raw as FrappeDataEnvelope<T>;
  const nestedMessage =
    typeof value.message === 'object' && value.message !== null
      ? value.message
      : undefined;
  const rootMessage =
    typeof value.message === 'string'
      ? value.message
      : undefined;

  if (nestedMessage?.success === false) {
    throw new Error(
      nestedMessage.message || 'AI conversation request failed',
    );
  }

  if (value.success === false) {
    throw new Error(
      rootMessage || 'AI conversation request failed',
    );
  }

  return (
    nestedMessage?.data
    ?? value.data
    ?? raw
  ) as T;
}

async function conversationRequest<T>(opts: {
  path: string;
  method?: 'GET' | 'POST';
  role: string;
  company: string;
  clientUserId?: string;
  body?: Record<string, unknown>;
}): Promise<T> {
  const headers = resolveAgentHeaders(
    opts.role,
    opts.company,
    opts.clientUserId,
  );

  const response = await fetch(
    `${API_BASE}/api/method/${opts.path}`,
    {
      method: opts.method ?? 'POST',
      headers,
      body:
        (opts.method ?? 'POST') === 'GET'
          ? undefined
          : JSON.stringify(opts.body ?? {}),
    },
  );

  const raw = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      typeof raw?.message === 'string'
        ? raw.message
        : `AI conversation error ${response.status}`,
    );
  }

  return unwrapFrappeData<T>(raw);
}

export async function createAgentConversation(opts: {
  role: string;
  company: string;
  clientUserId?: string;
  title?: string;
}): Promise<AgentConversationSummary> {
  return conversationRequest<AgentConversationSummary>({
    path: 'dms.api.ai_agent.create_conversation',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
    body: { title: opts.title ?? '' },
  });
}

export async function listAgentConversations(opts: {
  role: string;
  company: string;
  clientUserId?: string;
}): Promise<AgentConversationSummary[]> {
  return conversationRequest<AgentConversationSummary[]>({
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
  return conversationRequest<AgentConversationDetail>({
    path: 'dms.api.ai_agent.get_conversation',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
    body: { conversation_id: opts.conversationId },
  });
}

export async function archiveAgentConversation(opts: {
  conversationId: string;
  role: string;
  company: string;
  clientUserId?: string;
}): Promise<{ id: string; status: string }> {
  return conversationRequest<{ id: string; status: string }>({
    path: 'dms.api.ai_agent.archive_conversation',
    role: opts.role,
    company: opts.company,
    clientUserId: opts.clientUserId,
    body: { conversation_id: opts.conversationId },
  });
}
