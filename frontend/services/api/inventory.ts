import { apiClient, unwrapFrappe } from './client';

export interface VehicleInventoryRow {
  name: string;
  company_id: string;
  company_name: string;
  vehicle_name?: string | null;
  model: string;
  variant: string;
  color: string;
  year?: number | null;
  fuel_type?: string | null;
  transmission?: string | null;
  chassis_no?: string | null;
  engine_no?: string | null;
  ex_showroom_price?: number | null;
  on_road_price?: number | null;
  stock_status?: string | null;
  image?: string | null;
}

export interface VehicleInventoryResponse {
  rows: VehicleInventoryRow[];
  total: number;
  scope_label: string;
  is_group_admin: boolean;
  company_id?: string | null;
  company_counts: Record<string, number>;
  status_counts: Record<string, number>;
  data_source: string;
  session_user: string;
}

export async function getVehicleInventory(): Promise<VehicleInventoryResponse> {
  const { data } = await apiClient.get(
    '/method/dms.api.inventory.list_inventory',
  );
  return unwrapFrappe<VehicleInventoryResponse>(data);
}
