'use client';
import {
  ShoppingCart, DollarSign, Users, Car, Wrench, TrendingUp,
} from 'lucide-react';
import { KPICard, KPICardGrid } from '@/components/cards/KPICard';
import { SalesTrendChart } from '@/components/charts/SalesTrendChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { LeadSourcePieChart } from '@/components/charts/LeadSourcePieChart';
import { useHondaDashboard } from '@/hooks/useDashboard';
import { Skeleton } from '@/components/ui/skeleton';

const HONDA_RED = '#E40521';

const FALLBACK_LEAD_SOURCES = [
  { name: 'Website', value: 35, color: '#E40521' },
  { name: 'Walk-in', value: 25, color: '#FF6B6B' },
  { name: 'Referral', value: 20, color: '#FFA500' },
  { name: 'Social Media', value: 12, color: '#FFD700' },
  { name: 'Campaign', value: 8, color: '#FF8C00' },
];

export default function HondaDashboardPage() {
  const { data, isLoading } = useHondaDashboard();

  const kpis = data?.kpis;
  const charts = data?.charts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Honda Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          Overview of Honda dealership performance
        </p>
      </div>

      <KPICardGrid>
        <KPICard
          metric={kpis?.todays_sales ?? { label: "Today's Sales", value: 0, change: 0, change_type: 'neutral' }}
          icon={ShoppingCart}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.monthly_revenue ?? { label: 'Monthly Revenue', value: 0, change: 0, change_type: 'neutral', prefix: '₹' }}
          icon={DollarSign}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.total_leads ?? { label: 'Total Leads', value: 0, change: 0, change_type: 'neutral' }}
          icon={Users}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.test_drives ?? { label: 'Test Drives', value: 0, change: 0, change_type: 'neutral' }}
          icon={Car}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.service_revenue ?? { label: 'Service Revenue', value: 0, change: 0, change_type: 'neutral', prefix: '₹' }}
          icon={Wrench}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.conversion_rate ?? { label: 'Conversion Rate', value: 0, change: 0, change_type: 'neutral', suffix: '%' }}
          icon={TrendingUp}
          iconColor={HONDA_RED}
          loading={isLoading}
        />
      </KPICardGrid>

      <div className="grid gap-4 lg:grid-cols-2">
        {isLoading ? (
          <>
            <Skeleton className="h-80" />
            <Skeleton className="h-80" />
          </>
        ) : (
          <>
            <SalesTrendChart
              data={charts?.monthly_sales_trend ?? []}
              title="Monthly Sales Trend"
              color={HONDA_RED}
            />
            <RevenueTrendChart
              data={charts?.revenue_trend ?? []}
              title="Revenue Trend"
              color={HONDA_RED}
            />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {isLoading ? (
          <>
            <Skeleton className="h-72" />
            <Skeleton className="h-72 lg:col-span-2" />
          </>
        ) : (
          <>
            <LeadSourcePieChart
              data={charts?.lead_sources ?? FALLBACK_LEAD_SOURCES}
              title="Lead Sources"
            />
            <SalesTrendChart
              data={charts?.sales_conversion ?? []}
              title="Sales Conversion"
              color="#FF6B35"
              className="lg:col-span-2"
            />
          </>
        )}
      </div>
    </div>
  );
}
