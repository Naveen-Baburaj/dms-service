'use client';
import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { authApi } from '@/services/api/auth';
import { tokenStorage } from '@/services/api/client';
import { getDashboardRoute } from '@/types';
import type { LoginCredentials } from '@/types';

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setAuth, clearAuth, setLoading } = useAuthStore();

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onMutate: () => setLoading(true),
    onSuccess: ({ user, tokens }) => {
      setAuth(user, tokens);
      router.push(getDashboardRoute(user.company));
    },
    onError: () => setLoading(false),
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      clearAuth();
      tokenStorage.clearTokens();
      router.push('/login');
    },
  });

  const login = useCallback(
    (credentials: LoginCredentials) => loginMutation.mutate(credentials),
    [loginMutation],
  );

  const logout = useCallback(() => logoutMutation.mutate(), [logoutMutation]);

  return {
    user,
    isAuthenticated,
    isLoading: isLoading || loginMutation.isPending,
    login,
    logout,
    loginError: loginMutation.error,
  };
}
