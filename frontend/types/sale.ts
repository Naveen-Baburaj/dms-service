export type SaleStatus = 'Draft' | 'Confirmed' | 'Delivered' | 'Cancelled';
export type PaymentMode = 'Cash' | 'Finance' | 'Exchange' | 'Lease';

export interface VehicleSale {
  id: string;
  name: string;
  customer_id: string;
  customer_name: string;
  vehicle_id: string;
  vehicle_name: string;
  model: string;
  variant: string;
  color: string;
  chassis_no: string;
  engine_no: string;
  sale_price: number;
  discount: number;
  final_price: number;
  payment_mode: PaymentMode;
  status: SaleStatus;
  company_id: string;
  company_name: string;
  sales_consultant?: string;
  delivery_date?: string;
  invoice_no?: string;
  created_at: string;
}

export interface CreateSaleDTO {
  customer_id: string;
  vehicle_id: string;
  sale_price: number;
  discount?: number;
  payment_mode: PaymentMode;
  delivery_date?: string;
}

export interface SalesListResponse {
  data: VehicleSale[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SalesFilter {
  status?: SaleStatus;
  payment_mode?: PaymentMode;
  search?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
}

export interface Booking {
  id: string;
  customer_id: string;
  customer_name: string;
  vehicle_id: string;
  model: string;
  variant: string;
  color: string;
  booking_amount: number;
  booking_date: string;
  expected_delivery?: string;
  status: 'Pending' | 'Confirmed' | 'Cancelled' | 'Converted';
  company_id: string;
  created_at: string;
}

export interface TestDrive {
  id: string;
  lead_id?: string;
  customer_id?: string;
  contact_name: string;
  mobile_no: string;
  vehicle_id: string;
  model: string;
  scheduled_date: string;
  scheduled_time: string;
  status: 'Scheduled' | 'Completed' | 'Cancelled' | 'No Show';
  feedback?: string;
  rating?: number;
  company_id: string;
  created_at: string;
}
