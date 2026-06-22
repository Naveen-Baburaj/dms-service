import { apiClient, tokenStorage } from './client';
import type { LoginCredentials, LoginResponse, RefreshResponse, User, AuthTokens } from '@/types';

// ─── Mock users (no backend required) ────────────────────────────────────────
const MOCK_USERS: Record<string, { password: string; user: User }> = {
  'honda.manager@dms.local': {
    password: 'honda123',
    user: { id: 'u1', email: 'honda.manager@dms.local', full_name: 'Rahul Sharma', role: 'honda_manager', company: 'Honda', company_id: 'HONDA-00001', is_active: true },
  },
  'nexa.manager@dms.local': {
    password: 'nexa123',
    user: { id: 'u2', email: 'nexa.manager@dms.local', full_name: 'Priya Mehta', role: 'nexa_manager', company: 'NEXA', company_id: 'NEXA-00001', is_active: true },
  },
  'jaguar.manager@dms.local': {
    password: 'jaguar123',
    user: { id: 'u3', email: 'jaguar.manager@dms.local', full_name: 'Arjun Kapoor', role: 'jaguar_manager', company: 'Jaguar', company_id: 'JAG-00001', is_active: true },
  },
  'admin@dms.local': {
    password: 'admin123',
    user: { id: 'u4', email: 'admin@dms.local', full_name: 'Admin User', role: 'group_admin', company: 'Group', company_id: 'GROUP-00001', is_active: true },
  },
};

function makeMockJWT(user: User): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).replace(/=/g, '');
  const payload = btoa(JSON.stringify({
    sub: user.email,
    email: user.email,
    full_name: user.full_name,
    role: user.role,
    company: user.company,
    company_id: user.company_id,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 86400 * 30,
  })).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${header}.${payload}.mock_sig`;
}

function mockLogin(credentials: LoginCredentials): LoginResponse | null {
  const entry = MOCK_USERS[credentials.email.toLowerCase()];
  if (!entry) return null; // unknown email — fall through to real backend
  if (entry.password !== credentials.password) throw new Error('Invalid credentials. Please try again.');
  const accessToken = makeMockJWT(entry.user);
  const tokens: AuthTokens = { access_token: accessToken, refresh_token: 'mock_refresh', expires_in: 28800, token_type: 'Bearer' };
  // Set cookie so Next.js middleware lets dashboard routes through
  if (typeof document !== 'undefined') {
    document.cookie = `dms_access_token=${accessToken}; path=/; max-age=${86400 * 30}; SameSite=Lax`;
  }
  return { user: entry.user, tokens };
}
// ─────────────────────────────────────────────────────────────────────────────

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    // Try mock login first
    const mock = mockLogin(credentials);
    if (mock) {
      tokenStorage.setTokens(mock.tokens.access_token, mock.tokens.refresh_token);
      return mock;
    }

    // Fall through to real backend
    const { data } = await apiClient.post<{ success: boolean; data: LoginResponse }>(
      '/login',
      credentials,
    );
    const result = data.data;
    tokenStorage.setTokens(result.tokens.access_token, result.tokens.refresh_token);
    return result;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/logout');
    } catch {
      // backend may not be running — ignore
    } finally {
      tokenStorage.clearTokens();
      if (typeof document !== 'undefined') {
        document.cookie = 'dms_access_token=; path=/; max-age=0';
      }
    }
  },

  refresh: async (refreshToken: string): Promise<RefreshResponse> => {
    const { data } = await apiClient.post<{ success: boolean; data: RefreshResponse }>('/refresh', {
      refresh_token: refreshToken,
    });
    return data.data;
  },

  me: async () => {
    const { data } = await apiClient.get('/me');
    return data.data;
  },
};
