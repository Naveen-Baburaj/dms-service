import { apiClient, unwrapFrappe } from './client';
import type { Lead, CreateLeadDTO, UpdateLeadDTO, LeadsListResponse, LeadsFilter } from '@/types';

export const leadsApi = {
  getAll: async (filters: LeadsFilter = {}): Promise<LeadsListResponse> => {
    const { data } = await apiClient.get('/method/dms.api.frontend_demo.records', {
      params: { resource: 'leads', ...filters },
    });
    return unwrapFrappe<LeadsListResponse>(data);
  },

  getById: async (id: string): Promise<Lead> => {
    const result = await leadsApi.getAll({ page: 1, page_size: 200 });
    const lead = result.data.find((item) => item.id === id || item.name === id);
    if (!lead) throw new Error('Lead not found');
    return lead;
  },

  create: async (_payload: CreateLeadDTO): Promise<Lead> => {
    throw new Error('Create lead is not connected in demo mode yet.');
  },

  update: async (_payload: UpdateLeadDTO): Promise<Lead> => {
    throw new Error('Update lead is not connected in demo mode yet.');
  },

  delete: async (_id: string): Promise<void> => {
    throw new Error('Delete lead is disabled in demo mode.');
  },

  convertToCustomer: async (_id: string): Promise<{ customer_id: string }> => {
    throw new Error('Lead conversion is not connected in demo mode yet.');
  },
};
