export type LeadStatus =
  | 'New'
  | 'Open'
  | 'Replied'
  | 'Opportunity'
  | 'Quotation'
  | 'Converted'
  | 'Do Not Contact'
  | 'Lost';

export type LeadSource =
  | 'Website'
  | 'Cold Calling'
  | 'Referral'
  | 'Social Media'
  | 'Walk-in'
  | 'Exhibition'
  | 'Campaign'
  | 'Digital';

export interface Lead {
  id: string;
  name: string;
  lead_name: string;
  email: string;
  mobile_no: string;
  status: LeadStatus;
  source: LeadSource;
  company_id: string;
  company_name: string;
  vehicle_interest?: string;
  budget?: number;
  notes?: string;
  assigned_to?: string;
  follow_up_date?: string;
  created_at: string;
  modified_at: string;
}

export interface CreateLeadDTO {
  lead_name: string;
  email: string;
  mobile_no: string;
  status?: LeadStatus;
  source?: LeadSource;
  vehicle_interest?: string;
  budget?: number;
  notes?: string;
}

export interface UpdateLeadDTO extends Partial<CreateLeadDTO> {
  id: string;
}

export interface LeadsListResponse {
  data: Lead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LeadsFilter {
  status?: LeadStatus;
  source?: LeadSource;
  search?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  assigned_to?: string;
}
