import { apiClient } from './client';
import type { VehicleSale, CreateSaleDTO, SalesListResponse, SalesFilter, Booking, TestDrive } from '@/types';

export const salesApi = {
  getAll: async (filters: SalesFilter = {}): Promise<SalesListResponse> => {
    const { data } = await apiClient.get<{ success: boolean; data: SalesListResponse }>('/sales', {
      params: filters,
    });
    return data.data;
  },

  getById: async (id: string): Promise<VehicleSale> => {
    const { data } = await apiClient.get<{ success: boolean; data: VehicleSale }>(`/sales/${id}`);
    return data.data;
  },

  create: async (payload: CreateSaleDTO): Promise<VehicleSale> => {
    const { data } = await apiClient.post<{ success: boolean; data: VehicleSale }>(
      '/sales',
      payload,
    );
    return data.data;
  },

  updateStatus: async (id: string, status: VehicleSale['status']): Promise<VehicleSale> => {
    const { data } = await apiClient.patch<{ success: boolean; data: VehicleSale }>(
      `/sales/${id}/status`,
      { status },
    );
    return data.data;
  },

  getBookings: async (filters = {}): Promise<{ data: Booking[]; total: number }> => {
    const { data } = await apiClient.get('/bookings', { params: filters });
    return data.data;
  },

  getTestDrives: async (filters = {}): Promise<{ data: TestDrive[]; total: number }> => {
    const { data } = await apiClient.get('/test-drives', { params: filters });
    return data.data;
  },
};
