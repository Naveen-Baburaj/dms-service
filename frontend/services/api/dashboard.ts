import { apiClient, unwrapFrappe } from './client';
import type { HondaDashboard, NexaDashboard, JaguarDashboard, GroupDashboard } from '@/types';

async function getDashboard<T>(company: string): Promise<T> {
  const { data } = await apiClient.get('/method/dms.api.frontend_demo.dashboard', {
    params: { company },
  });
  return unwrapFrappe<T>(data);
}

export const dashboardApi = {
  honda: async (): Promise<HondaDashboard> => getDashboard<HondaDashboard>('Honda'),
  nexa: async (): Promise<NexaDashboard> => getDashboard<NexaDashboard>('NEXA'),
  jaguar: async (): Promise<JaguarDashboard> => getDashboard<JaguarDashboard>('Jaguar'),
  group: async (): Promise<GroupDashboard> => getDashboard<GroupDashboard>('Group'),
};
