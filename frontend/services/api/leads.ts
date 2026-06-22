import { apiClient } from './client';
import type { Lead, CreateLeadDTO, UpdateLeadDTO, LeadsListResponse, LeadsFilter } from '@/types';

export const leadsApi = {
  getAll: async (filters: LeadsFilter = {}): Promise<LeadsListResponse> => {
    const { data } = await apiClient.get<{ success: boolean; data: LeadsListResponse }>('/leads', {
      params: filters,
    });
    return data.data;
  },

  getById: async (id: string): Promise<Lead> => {
    const { data } = await apiClient.get<{ success: boolean; data: Lead }>(`/leads/${id}`);
    return data.data;
  },

  create: async (payload: CreateLeadDTO): Promise<Lead> => {
    const { data } = await apiClient.post<{ success: boolean; data: Lead }>('/leads', payload);
    return data.data;
  },

  update: async ({ id, ...payload }: UpdateLeadDTO): Promise<Lead> => {
    const { data } = await apiClient.put<{ success: boolean; data: Lead }>(`/leads/${id}`, payload);
    return data.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/leads/${id}`);
  },

  convertToCustomer: async (id: string): Promise<{ customer_id: string }> => {
    const { data } = await apiClient.post(`/leads/${id}/convert`);
    return data.data;
  },
};
