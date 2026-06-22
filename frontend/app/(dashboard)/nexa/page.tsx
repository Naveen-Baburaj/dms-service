'use client';
import { DollarSign, Car, Users, CalendarCheck, Star, TrendingUp } from 'lucide-react';
import { KPICard, KPICardGrid } from '@/components/cards/KPICard';
import { SalesTrendChart } from '@/components/charts/SalesTrendChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { LeadSourcePieChart } from '@/components/charts/LeadSourcePieChart';
import { useNexaDashboard } from '@/hooks/useDashboard';
import { Skeleton } from '@/components/ui/skeleton';

const NEXA_BLUE = '#1B4F8A';

const FALLBACK_LEAD_SOURCES = [
  { name: 'Digital', value: 40, color: '#1B4F8A' },
  { name: 'Referral', value: 22, color: '#2563B0' },
  { name: 'Walk-in', value: 18, color: '#3B82F6' },
  { name: 'Campaign', value: 12, color: '#60A5FA' },
  { name: 'Other', value: 8, color: '#93C5FD' },
];

export default function NexaDashboardPage() {
  const { data, isLoading } = useNexaDashboard();
  const kpis = data?.kpis;
  const charts = data?.charts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">NEXA Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          Overview of NEXA dealership performance
        </p>
      </div>

      <KPICardGrid>
        <KPICard
          metric={kpis?.revenue ?? { label: 'Revenue', value: 0, change: 0, change_type: 'neutral', prefix: '₹' }}
          icon={DollarSign}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.vehicle_sales ?? { label: 'Vehicle Sales', value: 0, change: 0, change_type: 'neutral' }}
          icon={Car}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.total_leads ?? { label: 'Total Leads', value: 0, change: 0, change_type: 'neutral' }}
          icon={Users}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.test_drives ?? { label: 'Test Drives', value: 0, change: 0, change_type: 'neutral' }}
          icon={CalendarCheck}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.bookings ?? { label: 'Bookings', value: 0, change: 0, change_type: 'neutral' }}
          icon={TrendingUp}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.customer_satisfaction ?? { label: 'Customer Satisfaction', value: 0, change: 0, change_type: 'neutral', suffix: '/5' }}
          icon={Star}
          iconColor={NEXA_BLUE}
          loading={isLoading}
        />
      </KPICardGrid>

      <div className="grid gap-4 lg:grid-cols-2">
        {isLoading ? (
          <><Skeleton className="h-80" /><Skeleton className="h-80" /></>
        ) : (
          <>
            <RevenueTrendChart data={charts?.revenue_trend ?? []} title="Revenue Trend" color={NEXA_BLUE} />
            <SalesTrendChart data={charts?.vehicle_sales_trend ?? []} title="Vehicle Sales Trend" color={NEXA_BLUE} />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {isLoading ? (
          <><Skeleton className="h-72" /><Skeleton className="h-72 lg:col-span-2" /></>
        ) : (
          <>
            <LeadSourcePieChart data={charts?.lead_sources ?? FALLBACK_LEAD_SOURCES} title="Lead Sources" />
            <SalesTrendChart data={charts?.sales_performance ?? []} title="Sales Performance" color="#2563B0" className="lg:col-span-2" />
          </>
        )}
      </div>
    </div>
  );
}
