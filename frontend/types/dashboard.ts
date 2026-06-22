export interface KPIMetric {
  label: string;
  value: number | string;
  change: number;
  change_type: 'increase' | 'decrease' | 'neutral';
  prefix?: string;
  suffix?: string;
  icon?: string;
}

export interface ChartDataPoint {
  month: string;
  value: number;
  previous?: number;
}

export interface PieDataPoint {
  name: string;
  value: number;
  color: string;
}

export interface HondaDashboard {
  kpis: {
    todays_sales: KPIMetric;
    monthly_revenue: KPIMetric;
    total_leads: KPIMetric;
    test_drives: KPIMetric;
    service_revenue: KPIMetric;
    conversion_rate: KPIMetric;
  };
  charts: {
    monthly_sales_trend: ChartDataPoint[];
    revenue_trend: ChartDataPoint[];
    lead_sources: PieDataPoint[];
    sales_conversion: ChartDataPoint[];
  };
  recent_leads: RecentActivity[];
  recent_sales: RecentActivity[];
}

export interface NexaDashboard {
  kpis: {
    revenue: KPIMetric;
    vehicle_sales: KPIMetric;
    total_leads: KPIMetric;
    test_drives: KPIMetric;
    bookings: KPIMetric;
    customer_satisfaction: KPIMetric;
  };
  charts: {
    revenue_trend: ChartDataPoint[];
    vehicle_sales_trend: ChartDataPoint[];
    lead_sources: PieDataPoint[];
    sales_performance: ChartDataPoint[];
  };
  recent_leads: RecentActivity[];
  recent_sales: RecentActivity[];
}

export interface JaguarDashboard {
  kpis: {
    luxury_sales: KPIMetric;
    premium_customers: KPIMetric;
    revenue: KPIMetric;
    retention_rate: KPIMetric;
    test_drives: KPIMetric;
  };
  charts: {
    luxury_sales_trend: ChartDataPoint[];
    premium_customer_analytics: ChartDataPoint[];
    revenue_trend: ChartDataPoint[];
    customer_segmentation: PieDataPoint[];
  };
  recent_leads: RecentActivity[];
  recent_sales: RecentActivity[];
}

export interface GroupDashboard {
  kpis: {
    total_revenue: KPIMetric;
    total_leads: KPIMetric;
    total_sales: KPIMetric;
    total_customers: KPIMetric;
    active_users: KPIMetric;
  };
  charts: {
    revenue_by_company: CompanyChartData[];
    sales_by_company: CompanyChartData[];
    revenue_share: PieDataPoint[];
    monthly_revenue_trend: ChartDataPoint[];
    lead_comparison: CompanyChartData[];
    service_revenue_comparison: CompanyChartData[];
  };
  company_summary: CompanySummary[];
}

export interface CompanyChartData {
  month: string;
  honda: number;
  nexa: number;
  jaguar: number;
}

export interface CompanySummary {
  company: string;
  revenue: number;
  sales: number;
  leads: number;
  customers: number;
  growth: number;
}

export interface RecentActivity {
  id: string;
  type: 'lead' | 'sale' | 'booking' | 'test_drive';
  title: string;
  subtitle: string;
  amount?: number;
  status: string;
  created_at: string;
}
