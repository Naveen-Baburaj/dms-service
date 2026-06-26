import { resolveAgentHeaders } from './aiAgent';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://dms.localhost:8000';

export type RpaSaveTarget = 'dms' | 'ghl' | 'both';

export interface RpaContactPayload {
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  vehicle_interest?: string;
  source?: string;
  notes?: string;
}

export interface GhlSessionStatus {
  session_name: string;
  status: 'Active' | 'Login Required' | string;
  storage_state_exists: boolean;
  storage_state_path?: string;
  contacts_url?: string;
  deep_check?: boolean;
  current_url?: string;
}

export interface GhlLoginResult {
  session_name: string;
  status: string;
  storage_state_path?: string;
  contacts_url?: string;
  current_url?: string;
  screenshot?: string | null;
  message?: string;
}

export interface RpaSaveResult {
  target: RpaSaveTarget;
  status: 'Success' | 'Failed' | 'Login Required' | string;
  message: string;
  dms_contact?: string | null;
  rpa_job?: string | null;
  ghl_result?: {
    success?: boolean;
    status?: string;
    message?: string;
    contact_name?: string | null;
    contact_url?: string | null;
    screenshot_before?: string | null;
    screenshot_after?: string | null;
    details?: Record<string, unknown> | null;
  } | null;
}

export interface RpaJobStatus {
  name: string;
  provider?: string;
  job_type?: string;
  status?: string;
  save_target?: string;
  contact?: string;
  session_name?: string;
  contacts_url?: string;
  tag_name?: string;
  payload_json?: string;
  result_json?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface RpaSavedContact {
  name: string;
  contact_name?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  vehicle_interest?: string;
  source?: string;
  save_target?: string;
  ghl_tag?: string;
  ghl_sync_status?: string;
  ghl_sync_message?: string;
  ghl_contact_url?: string;
  rpa_job?: string;
  last_synced_at?: string;
  modified?: string;
}

export interface RpaContactListResult {
  rows: RpaSavedContact[];
  total: number;
  limit?: number;
  search?: string | null;
}

type FrappeRpaEnvelope<T> = {
  message?: {
    success?: boolean;
    data?: T;
    message?: string;
    details?: string | null;
  } | string;
  success?: boolean;
  data?: T;
  details?: string | null;
};

function unwrapFrappe<T>(raw: unknown): T {
  const value = raw as FrappeRpaEnvelope<T>;
  const nestedMessage =
    typeof value.message === 'object' && value.message !== null
      ? value.message
      : undefined;
  const rootMessage = typeof value.message === 'string' ? value.message : undefined;

  if (nestedMessage?.success === false) {
    throw new Error(nestedMessage.message || nestedMessage.details || 'RPA request failed');
  }

  if (value.success === false) {
    throw new Error(rootMessage || value.details || 'RPA request failed');
  }

  return (nestedMessage?.data ?? value.data ?? raw) as T;
}

async function postRpa<T>(opts: {
  endpoint: string;
  role: string;
  company: string;
  body?: Record<string, unknown>;
  timeoutMs?: number;
}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), opts.timeoutMs ?? 120000);

  try {
    const headers = resolveAgentHeaders(opts.role, opts.company);
    const response = await fetch(`${API_BASE}/api/method/${opts.endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(opts.body ?? {}),
      signal: controller.signal,
    });

    const raw = await response.json().catch(() => null);

    if (!response.ok) {
      const msg =
        typeof raw?.message === 'string'
          ? raw.message
          : raw?.message?.message || raw?.exception || `RPA API error ${response.status}`;
      throw new Error(msg);
    }

    return unwrapFrappe<T>(raw);
  } finally {
    window.clearTimeout(timeout);
  }
}

export function checkGhlSession(opts: {
  role: string;
  company: string;
  deepCheck?: boolean;
}): Promise<GhlSessionStatus> {
  return postRpa<GhlSessionStatus>({
    endpoint: 'dms.api.rpa_gohighlevel.check_session',
    role: opts.role,
    company: opts.company,
    body: { deep_check: Boolean(opts.deepCheck) },
    timeoutMs: opts.deepCheck ? 90000 : 30000,
  });
}

export function openGhlLogin(opts: {
  role: string;
  company: string;
  timeoutSeconds?: number;
}): Promise<GhlLoginResult> {
  return postRpa<GhlLoginResult>({
    endpoint: 'dms.api.rpa_gohighlevel.open_login',
    role: opts.role,
    company: opts.company,
    body: { timeout_seconds: opts.timeoutSeconds ?? 600 },
    timeoutMs: (opts.timeoutSeconds ?? 600) * 1000 + 30000,
  });
}

export function saveRpaContact(opts: {
  role: string;
  company: string;
  target: RpaSaveTarget;
  contact: RpaContactPayload;
}): Promise<RpaSaveResult> {
  return postRpa<RpaSaveResult>({
    endpoint: 'dms.api.rpa_gohighlevel.save_contact',
    role: opts.role,
    company: opts.company,
    body: {
      target: opts.target,
      contact: opts.contact,
    },
    timeoutMs: opts.target === 'dms' ? 60000 : 240000,
  });
}

export function listRpaContacts(opts: {
  role: string;
  company: string;
  limit?: number;
  search?: string;
}): Promise<RpaContactListResult> {
  return postRpa<RpaContactListResult>({
    endpoint: 'dms.api.rpa_gohighlevel.list_contacts',
    role: opts.role,
    company: opts.company,
    body: {
      limit: opts.limit ?? 25,
      search: opts.search?.trim() || undefined,
    },
    timeoutMs: 30000,
  });
}

export function getRpaJobStatus(opts: {
  role: string;
  company: string;
  jobId: string;
}): Promise<RpaJobStatus> {
  return postRpa<RpaJobStatus>({
    endpoint: 'dms.api.rpa_gohighlevel.get_job_status',
    role: opts.role,
    company: opts.company,
    body: { job_id: opts.jobId },
    timeoutMs: 30000,
  });
}
