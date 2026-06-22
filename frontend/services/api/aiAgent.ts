const AI_BASE = process.env.NEXT_PUBLIC_AI_AGENT_URL ?? 'http://127.0.0.1:8000';

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

// Maps DMS company names to backend demo tenant IDs.
// Update to 'honda', 'nexa', 'jaguar' once the backend uses production data.
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
  return headers;
}

export async function queryDashboardAgent(opts: {
  query: string;
  role: string;
  company: string;
}): Promise<AgentResponse> {
  const headers = resolveAgentHeaders(opts.role, opts.company);

  const res = await fetch(`${AI_BASE}/api/v1/agent/query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query: opts.query }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText);
    throw new Error(`AI agent error ${res.status}: ${body}`);
  }

  return res.json() as Promise<AgentResponse>;
}
