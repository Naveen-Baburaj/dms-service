import { apiClient, unwrapFrappe } from './client';

export interface CadenceLaunch {
  launch_url: string;
  token: string;
  expires_in: number;
  scope: 'admin' | 'tenant';
  tenant_slug?: string | null;
}

export async function createCadenceLaunch(): Promise<CadenceLaunch> {
  const { data } = await apiClient.post('/method/dms.api.cadence.launch');
  return unwrapFrappe<CadenceLaunch>(data);
}
