import { apiClient } from './client';
import type { HondaDashboard, NexaDashboard, JaguarDashboard, GroupDashboard } from '@/types';

export const dashboardApi = {
  honda: async (): Promise<HondaDashboard> => {
    const { data } = await apiClient.get<{ success: boolean; data: HondaDashboard }>(
      '/dashboard/honda',
    );
    return data.data;
  },

  nexa: async (): Promise<NexaDashboard> => {
    const { data } = await apiClient.get<{ success: boolean; data: NexaDashboard }>(
      '/dashboard/nexa',
    );
    return data.data;
  },

  jaguar: async (): Promise<JaguarDashboard> => {
    const { data } = await apiClient.get<{ success: boolean; data: JaguarDashboard }>(
      '/dashboard/jaguar',
    );
    return data.data;
  },

  group: async (): Promise<GroupDashboard> => {
    const { data } = await apiClient.get<{ success: boolean; data: GroupDashboard }>(
      '/dashboard/group',
    );
    return data.data;
  },
};
