export type CustomerType = 'Individual' | 'Corporate';
export type CustomerStatus = 'Active' | 'Inactive';

export interface Customer {
  id: string;
  name: string;
  customer_name: string;
  email: string;
  mobile_no: string;
  customer_type: CustomerType;
  status: CustomerStatus;
  company_id: string;
  company_name: string;
  address?: string;
  city?: string;
  state?: string;
  pin_code?: string;
  dob?: string;
  anniversary?: string;
  total_purchases: number;
  last_purchase_date?: string;
  loyalty_points: number;
  created_at: string;
}

export interface CreateCustomerDTO {
  customer_name: string;
  email: string;
  mobile_no: string;
  customer_type?: CustomerType;
  address?: string;
  city?: string;
  state?: string;
  pin_code?: string;
  dob?: string;
}

export interface CustomersListResponse {
  data: Customer[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CustomersFilter {
  status?: CustomerStatus;
  customer_type?: CustomerType;
  search?: string;
  page?: number;
  page_size?: number;
}
