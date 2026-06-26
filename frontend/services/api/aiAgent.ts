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

export function resolveAgentHeaders(role: string, company: string): Record<string, string> {
  const xUserRole = ROLE_MAP[role] ?? 'tenant_user';

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'x-user-role': xUserRole,
  };

  if (xUserRole === 'tenant_user') {
    headers['x-tenant-id'] = TENANT_MAP[company] ?? company.toLowerCase();
  }

  const token = tokenStorage.getAccess();

  // Demo mock JWTs are only for the Next.js frontend middleware.
  // Do not send them to Frappe because Frappe will reject the fake signature.
  if (token && !isMockToken(token)) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

function unwrapFrappeResponse(raw: unknown): AgentResponse {
  const value = raw as {
    message?: {
      success?: boolean;
      data?: AgentResponse;
      message?: string;
    };
    success?: boolean;
    data?: AgentResponse;
    message?: string;
  };

  if (value.message?.success === false) {
    throw new Error(value.message.message || 'AI agent request failed');
  }

  if (value.success === false) {
    throw new Error(value.message || 'AI agent request failed');
  }

  const data = value.message?.data ?? value.data ?? raw;

  return data as AgentResponse;
}

export async function queryDashboardAgent(opts: {
  query: string;
  role: string;
  company: string;
}): Promise<AgentResponse> {
  const headers = resolveAgentHeaders(opts.role, opts.company);

  const res = await fetch(`${API_BASE}/api/method/dms.api.ai_agent.query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query: opts.query }),
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
