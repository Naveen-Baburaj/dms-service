'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';

import { authApi } from '@/services/api/auth';
import { useAuthStore } from '@/store/authStore';
import { getDashboardRoute } from '@/types';
import type { LoginCredentials } from '@/types';

export function useAuth() {
  const router = useRouter();
  const {
    user,
    isAuthenticated,
    isLoading,
    setAuth,
    clearAuth,
    setLoading,
  } = useAuthStore();

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onMutate: () => setLoading(true),
    onSuccess: ({ user: authenticatedUser }) => {
      setAuth(authenticatedUser);
      router.push(getDashboardRoute(authenticatedUser.company));
    },
    onError: () => setLoading(false),
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      clearAuth();
      router.push('/login');
    },
  });

  const login = useCallback(
    (credentials: LoginCredentials) => loginMutation.mutate(credentials),
    [loginMutation],
  );

  const logout = useCallback(
    () => logoutMutation.mutate(),
    [logoutMutation],
  );

  return {
    user,
    isAuthenticated,
    isLoading: isLoading || loginMutation.isPending,
    login,
    logout,
    loginError: loginMutation.error,
  };
}
