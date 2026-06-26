import { apiClient, unwrapFrappe } from './client';
import type {
  Customer,
  CreateCustomerDTO,
  CustomersListResponse,
  CustomersFilter,
} from '@/types';

export const customersApi = {
  getAll: async (filters: CustomersFilter = {}): Promise<CustomersListResponse> => {
    const { data } = await apiClient.get('/method/dms.api.frontend_demo.records', {
      params: { resource: 'customers', ...filters },
    });
    return unwrapFrappe<CustomersListResponse>(data);
  },

  getById: async (id: string): Promise<Customer> => {
    const result = await customersApi.getAll({ page: 1, page_size: 200 });
    const customer = result.data.find((item) => item.id === id || item.name === id);
    if (!customer) throw new Error('Customer not found');
    return customer;
  },

  create: async (_payload: CreateCustomerDTO): Promise<Customer> => {
    throw new Error('Create customer is not connected in demo mode yet.');
  },

  update: async (_id: string, _payload: Partial<CreateCustomerDTO>): Promise<Customer> => {
    throw new Error('Update customer is not connected in demo mode yet.');
  },

  getPurchaseHistory: async (_id: string) => {
    return [];
  },
};
