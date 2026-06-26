import { apiClient, unwrapFrappe } from './client';
import type { VehicleSale, CreateSaleDTO, SalesListResponse, SalesFilter, Booking, TestDrive } from '@/types';

export const salesApi = {
  getAll: async (filters: SalesFilter = {}): Promise<SalesListResponse> => {
    const { data } = await apiClient.get('/method/dms.api.frontend_demo.records', {
      params: { resource: 'sales', ...filters },
    });
    return unwrapFrappe<SalesListResponse>(data);
  },

  getById: async (id: string): Promise<VehicleSale> => {
    const result = await salesApi.getAll({ page: 1, page_size: 200 });
    const sale = result.data.find((item) => item.id === id || item.name === id);
    if (!sale) throw new Error('Sale not found');
    return sale;
  },

  create: async (_payload: CreateSaleDTO): Promise<VehicleSale> => {
    throw new Error('Create sale is not connected in demo mode yet.');
  },

  updateStatus: async (_id: string, _status: VehicleSale['status']): Promise<VehicleSale> => {
    throw new Error('Update sale status is not connected in demo mode yet.');
  },

  getBookings: async (filters = {}): Promise<{ data: Booking[]; total: number }> => {
    const { data } = await apiClient.get('/method/dms.api.frontend_demo.records', {
      params: { resource: 'bookings', ...filters },
    });
    return unwrapFrappe<{ data: Booking[]; total: number }>(data);
  },

  getTestDrives: async (filters = {}): Promise<{ data: TestDrive[]; total: number }> => {
    const { data } = await apiClient.get('/method/dms.api.frontend_demo.records', {
      params: { resource: 'test_drives', ...filters },
    });
    return unwrapFrappe<{ data: TestDrive[]; total: number }>(data);
  },
};
