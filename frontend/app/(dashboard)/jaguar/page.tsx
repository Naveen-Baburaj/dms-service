'use client';
import { Crown, Users, DollarSign, RefreshCw, Car, Star } from 'lucide-react';
import { KPICard, KPICardGrid } from '@/components/cards/KPICard';
import { SalesTrendChart } from '@/components/charts/SalesTrendChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { LeadSourcePieChart } from '@/components/charts/LeadSourcePieChart';
import { useJaguarDashboard } from '@/hooks/useDashboard';
import { Skeleton } from '@/components/ui/skeleton';

const JAGUAR_DARK = '#1A1A1A';
const JAGUAR_GOLD = '#C4A35A';

const FALLBACK_SEGMENTS = [
  { name: 'Ultra HNI', value: 30, color: '#1A1A1A' },
  { name: 'HNI', value: 45, color: '#C4A35A' },
  { name: 'Corporate', value: 15, color: '#4A4A4A' },
  { name: 'Other', value: 10, color: '#8A8A8A' },
];

export default function JaguarDashboardPage() {
  const { data, isLoading } = useJaguarDashboard();
  const kpis = data?.kpis;
  const charts = data?.charts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Jaguar Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          Premium luxury vehicle performance overview
        </p>
      </div>

      <KPICardGrid className="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KPICard
          metric={kpis?.luxury_sales ?? { label: 'Luxury Sales', value: 0, change: 0, change_type: 'neutral' }}
          icon={Crown}
          iconColor={JAGUAR_GOLD}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.premium_customers ?? { label: 'Premium Customers', value: 0, change: 0, change_type: 'neutral' }}
          icon={Users}
          iconColor={JAGUAR_DARK}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.revenue ?? { label: 'Revenue', value: 0, change: 0, change_type: 'neutral', prefix: '₹' }}
          icon={DollarSign}
          iconColor={JAGUAR_GOLD}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.retention_rate ?? { label: 'Retention Rate', value: 0, change: 0, change_type: 'neutral', suffix: '%' }}
          icon={RefreshCw}
          iconColor={JAGUAR_DARK}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.test_drives ?? { label: 'Test Drives', value: 0, change: 0, change_type: 'neutral' }}
          icon={Car}
          iconColor={JAGUAR_GOLD}
          loading={isLoading}
        />
      </KPICardGrid>

      <div className="grid gap-4 lg:grid-cols-2">
        {isLoading ? (
          <><Skeleton className="h-80" /><Skeleton className="h-80" /></>
        ) : (
          <>
            <SalesTrendChart data={charts?.luxury_sales_trend ?? []} title="Luxury Sales Trend" color={JAGUAR_GOLD} />
            <RevenueTrendChart data={charts?.revenue_trend ?? []} title="Revenue Trend" color={JAGUAR_DARK} />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {isLoading ? (
          <><Skeleton className="h-72" /><Skeleton className="h-72 lg:col-span-2" /></>
        ) : (
          <>
            <LeadSourcePieChart data={charts?.customer_segmentation ?? FALLBACK_SEGMENTS} title="Customer Segmentation" />
            <SalesTrendChart data={charts?.premium_customer_analytics ?? []} title="Premium Customer Analytics" color={JAGUAR_GOLD} className="lg:col-span-2" />
          </>
        )}
      </div>
    </div>
  );
}
