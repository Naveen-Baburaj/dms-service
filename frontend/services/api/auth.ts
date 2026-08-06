import { apiClient, csrfStorage, unwrapFrappe } from './client';
import type { LoginCredentials, LoginResponse, SessionResponse, User } from '@/types';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    const { data } = await apiClient.post(
      '/method/dms.api.auth.login',
      credentials,
    );
    const result = unwrapFrappe<LoginResponse>(data);
    csrfStorage.set(result.csrf_token);
    return result;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/method/dms.api.auth.logout');
    } finally {
      csrfStorage.clear();
    }
  },

  me: async (): Promise<User> => {
    const { data } = await apiClient.get('/method/dms.api.auth.me');
    const result = unwrapFrappe<SessionResponse>(data);
    csrfStorage.set(result.csrf_token);
    return result.user;
  },
};
