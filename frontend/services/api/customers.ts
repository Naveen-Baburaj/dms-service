import { apiClient } from './client';
import type {
  Customer,
  CreateCustomerDTO,
  CustomersListResponse,
  CustomersFilter,
} from '@/types';

export const customersApi = {
  getAll: async (filters: CustomersFilter = {}): Promise<CustomersListResponse> => {
    const { data } = await apiClient.get<{ success: boolean; data: CustomersListResponse }>(
      '/customers',
      { params: filters },
    );
    return data.data;
  },

  getById: async (id: string): Promise<Customer> => {
    const { data } = await apiClient.get<{ success: boolean; data: Customer }>(
      `/customers/${id}`,
    );
    return data.data;
  },

  create: async (payload: CreateCustomerDTO): Promise<Customer> => {
    const { data } = await apiClient.post<{ success: boolean; data: Customer }>(
      '/customers',
      payload,
    );
    return data.data;
  },

  update: async (id: string, payload: Partial<CreateCustomerDTO>): Promise<Customer> => {
    const { data } = await apiClient.put<{ success: boolean; data: Customer }>(
      `/customers/${id}`,
      payload,
    );
    return data.data;
  },

  getPurchaseHistory: async (id: string) => {
    const { data } = await apiClient.get(`/customers/${id}/purchases`);
    return data.data;
  },
};
