import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://dms.localhost:8000';

const ACCESS_TOKEN_KEY = 'dms_access_token';
const REFRESH_TOKEN_KEY = 'dms_refresh_token';

function isMockToken(token: string | null): boolean {
  return Boolean(token && (token.endsWith('.mock_sig') || token === 'mock_refresh'));
}

function getStoredUser(): { role?: string; company?: string } | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = localStorage.getItem('dms-auth');
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    return parsed?.state?.user ?? null;
  } catch {
    return null;
  }
}

function getDemoHeaders(): Record<string, string> {
  const user = getStoredUser();

  if (!user) return {};

  if (user.role === 'group_admin' || user.company === 'Group') {
    return { 'x-user-role': 'service_centre_admin' };
  }

  const tenantMap: Record<string, string> = {
    Honda: 'toyota',
    NEXA: 'suzuki',
    Jaguar: 'hyundai',
  };

  return {
    'x-user-role': 'tenant_user',
    'x-tenant-id': tenantMap[user.company ?? ''] ?? String(user.company ?? '').toLowerCase(),
  };
}

export const tokenStorage = {
  getAccess: (): string | null =>
    typeof window !== 'undefined' ? localStorage.getItem(ACCESS_TOKEN_KEY) : null,
  getRefresh: (): string | null =>
    typeof window !== 'undefined' ? localStorage.getItem(REFRESH_TOKEN_KEY) : null,
  setTokens: (access: string, refresh: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  },
  clearTokens: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject: (reason: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token!);
  });
  failedQueue = [];
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = tokenStorage.getAccess();

    config.headers = config.headers ?? {};

    const demoHeaders = getDemoHeaders();
    Object.entries(demoHeaders).forEach(([key, value]) => {
      config.headers[key] = value;
    });

    if (token && !isMockToken(token)) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      const accessToken = tokenStorage.getAccess();
      const refreshToken = tokenStorage.getRefresh();

      if (isMockToken(accessToken) || isMockToken(refreshToken)) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      if (!refreshToken) {
        tokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE_URL}/api/refresh`, {
          refresh_token: refreshToken,
        });
        const newToken: string = data.data.access_token;
        tokenStorage.setTokens(newToken, refreshToken);
        processQueue(null, newToken);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

type FrappeEnvelope<T> = {
  message?: {
    success?: boolean;
    data?: T;
    message?: string;
  } | string;
  success?: boolean;
  data?: T;
};

export function unwrapFrappe<T>(raw: unknown): T {
  const value = raw as FrappeEnvelope<T>;
  const nestedMessage =
    typeof value.message === 'object' && value.message !== null
      ? value.message
      : undefined;
  const rootMessage = typeof value.message === 'string' ? value.message : undefined;

  if (nestedMessage?.success === false) {
    throw new Error(nestedMessage.message || 'Request failed');
  }

  if (value.success === false) {
    throw new Error(rootMessage || 'Request failed');
  }

  return (nestedMessage?.data ?? value.data ?? raw) as T;
}
