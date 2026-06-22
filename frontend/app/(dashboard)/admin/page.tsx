'use client';
import { DollarSign, Users, ShoppingCart, UserCheck, Activity } from 'lucide-react';
import { KPICard, KPICardGrid } from '@/components/cards/KPICard';
import { CompanyComparisonChart } from '@/components/charts/CompanyComparisonChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { LeadSourcePieChart } from '@/components/charts/LeadSourcePieChart';
import { useGroupDashboard } from '@/hooks/useDashboard';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency, formatNumber } from '@/lib/utils';

const GROUP_BLUE = '#0F4C81';

const FALLBACK_REVENUE_SHARE = [
  { name: 'Honda', value: 45, color: '#E40521' },
  { name: 'NEXA', value: 38, color: '#1B4F8A' },
  { name: 'Jaguar', value: 17, color: '#555555' },
];

export default function AdminDashboardPage() {
  const { data, isLoading } = useGroupDashboard();
  const kpis = data?.kpis;
  const charts = data?.charts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Group Admin Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          Consolidated view across Honda, NEXA, and Jaguar
        </p>
      </div>

      <KPICardGrid>
        <KPICard
          metric={kpis?.total_revenue ?? { label: 'Total Revenue', value: 0, change: 0, change_type: 'neutral', prefix: '₹' }}
          icon={DollarSign}
          iconColor={GROUP_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.total_leads ?? { label: 'Total Leads', value: 0, change: 0, change_type: 'neutral' }}
          icon={Users}
          iconColor={GROUP_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.total_sales ?? { label: 'Total Sales', value: 0, change: 0, change_type: 'neutral' }}
          icon={ShoppingCart}
          iconColor={GROUP_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.total_customers ?? { label: 'Total Customers', value: 0, change: 0, change_type: 'neutral' }}
          icon={UserCheck}
          iconColor={GROUP_BLUE}
          loading={isLoading}
        />
        <KPICard
          metric={kpis?.active_users ?? { label: 'Active Users', value: 0, change: 0, change_type: 'neutral' }}
          icon={Activity}
          iconColor={GROUP_BLUE}
          loading={isLoading}
        />
      </KPICardGrid>

      {/* Company summary cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {isLoading ? (
          <><Skeleton className="h-40" /><Skeleton className="h-40" /><Skeleton className="h-40" /></>
        ) : (
          (data?.company_summary ?? [
            { company: 'Honda', revenue: 0, sales: 0, leads: 0, customers: 0, growth: 0 },
            { company: 'NEXA', revenue: 0, sales: 0, leads: 0, customers: 0, growth: 0 },
            { company: 'Jaguar', revenue: 0, sales: 0, leads: 0, customers: 0, growth: 0 },
          ]).map((cs) => {
            const colors: Record<string, string> = { Honda: '#E40521', NEXA: '#1B4F8A', Jaguar: '#555555' };
            const color = colors[cs.company] ?? '#0F4C81';
            return (
              <Card key={cs.company} className="overflow-hidden">
                <div className="h-1" style={{ backgroundColor: color }} />
                <CardHeader className="pb-2">
                  <CardTitle className="text-base" style={{ color }}>
                    {cs.company}
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-muted-foreground text-xs">Revenue</p>
                    <p className="font-semibold">{formatCurrency(cs.revenue)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs">Sales</p>
                    <p className="font-semibold">{formatNumber(cs.sales)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs">Leads</p>
                    <p className="font-semibold">{formatNumber(cs.leads)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs">Growth</p>
                    <p className={`font-semibold ${cs.growth >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                      {cs.growth >= 0 ? '+' : ''}{cs.growth}%
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {isLoading ? (
          <><Skeleton className="h-80" /><Skeleton className="h-80" /></>
        ) : (
          <>
            <CompanyComparisonChart data={charts?.revenue_by_company ?? []} title="Revenue by Company" dataKey="revenue" />
            <CompanyComparisonChart data={charts?.sales_by_company ?? []} title="Sales by Company" dataKey="sales" />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {isLoading ? (
          <><Skeleton className="h-72" /><Skeleton className="h-72 lg:col-span-2" /></>
        ) : (
          <>
            <LeadSourcePieChart data={charts?.revenue_share ?? FALLBACK_REVENUE_SHARE} title="Revenue Share" />
            <RevenueTrendChart data={charts?.monthly_revenue_trend ?? []} title="Monthly Revenue Trend" color={GROUP_BLUE} className="lg:col-span-2" />
          </>
        )}
      </div>
    </div>
  );
}
