export type UserRole =
  | 'honda_user'
  | 'honda_manager'
  | 'nexa_user'
  | 'nexa_manager'
  | 'jaguar_user'
  | 'jaguar_manager'
  | 'group_admin';

export type CompanyType = 'Honda' | 'NEXA' | 'Jaguar' | 'Group';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  company: CompanyType;
  company_id: string;
  avatar?: string;
  is_active: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: 'Bearer';
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  tokens: AuthTokens;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
}

export function getDashboardRoute(company: CompanyType): string {
  const routes: Record<CompanyType, string> = {
    Honda: '/honda',
    NEXA: '/nexa',
    Jaguar: '/jaguar',
    Group: '/admin',
  };
  return routes[company];
}

export function isManagerRole(role: UserRole): boolean {
  return role.endsWith('_manager') || role === 'group_admin';
}

export function isGroupAdmin(role: UserRole): boolean {
  return role === 'group_admin';
}

export function getCompanyColor(company: CompanyType): string {
  const colors: Record<CompanyType, string> = {
    Honda: '#E40521',
    NEXA: '#1B4F8A',
    Jaguar: '#1A1A1A',
    Group: '#0F4C81',
  };
  return colors[company];
}
