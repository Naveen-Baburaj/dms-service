import axios, { AxiosInstance, AxiosResponse } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://dms.localhost:8000';
const CSRF_TOKEN_KEY = 'dms_csrf_token';

export const csrfStorage = {
  get: (): string | null =>
    typeof window !== 'undefined' ? sessionStorage.getItem(CSRF_TOKEN_KEY) : null,
  set: (token: string): void => {
    if (typeof window !== 'undefined') sessionStorage.setItem(CSRF_TOKEN_KEY, token);
  },
  clear: (): void => {
    if (typeof window !== 'undefined') sessionStorage.removeItem(CSRF_TOKEN_KEY);
  },
};

function clearBrowserAuthState(): void {
  csrfStorage.clear();
  if (typeof window !== 'undefined') {
    localStorage.removeItem('dms-auth');
  }
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const method = String(config.method ?? 'get').toLowerCase();
    if (!['get', 'head', 'options'].includes(method)) {
      const csrfToken = csrfStorage.get();
      if (csrfToken) {
        config.headers = config.headers ?? {};
        config.headers['X-Frappe-CSRF-Token'] = csrfToken;
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const status = Number(error?.response?.status ?? 0);
    const url = String(error?.config?.url ?? '');
    const isLogin = url.includes('dms.api.auth.login');
    if ((status === 401 || status === 403) && !isLogin) {
      clearBrowserAuthState();
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
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
