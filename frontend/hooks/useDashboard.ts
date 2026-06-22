'use client';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/services/api/dashboard';
import { useAuthStore } from '@/store/authStore';

export function useHondaDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'honda'],
    queryFn: dashboardApi.honda,
    staleTime: 2 * 60 * 1000,
  });
}

export function useNexaDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'nexa'],
    queryFn: dashboardApi.nexa,
    staleTime: 2 * 60 * 1000,
  });
}

export function useJaguarDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'jaguar'],
    queryFn: dashboardApi.jaguar,
    staleTime: 2 * 60 * 1000,
  });
}

export function useGroupDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'group'],
    queryFn: dashboardApi.group,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCurrentDashboard() {
  const { user } = useAuthStore();
  const company = user?.company;

  const honda = useHondaDashboard();
  const nexa = useNexaDashboard();
  const jaguar = useJaguarDashboard();
  const group = useGroupDashboard();

  if (company === 'Honda') return honda;
  if (company === 'NEXA') return nexa;
  if (company === 'Jaguar') return jaguar;
  if (company === 'Group') return group;
  return honda;
}
