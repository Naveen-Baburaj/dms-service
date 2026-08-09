'use client';

import { Database } from 'lucide-react';

import { CompanyComparisonChart } from '@/components/charts/CompanyComparisonChart';
import { LeadSourcePieChart } from '@/components/charts/LeadSourcePieChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useGroupDashboard } from '@/hooks/useDashboard';
import { formatCurrency, formatNumber } from '@/lib/utils';

function numeric(value: number | string | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function GroupAnalyticsPage() {
  const { data, isLoading } = useGroupDashboard();
  const totalRevenue = numeric(data?.kpis.total_revenue.value);
  const totalLeads = numeric(data?.kpis.total_leads.value);
  const totalSales = numeric(data?.kpis.total_sales.value);
  const conversion = totalLeads > 0 ? (totalSales / totalLeads) * 100 : 0;

  const kpis = [
    { label: 'Group Revenue', value: formatCurrency(totalRevenue) },
    { label: 'Total Leads', value: formatNumber(totalLeads) },
    { label: 'Lead-to-Sale Ratio', value: `${conversion.toFixed(1)}%` },
    { label: 'Vehicles Sold', value: formatNumber(totalSales) },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Group Analytics</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          Live performance across Honda, NEXA, and Jaguar
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-5">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {kpi.label}
              </p>
              {isLoading ? (
                <Skeleton className="mt-2 h-8 w-28" />
              ) : (
                <p className="text-2xl font-bold mt-1">{kpi.value}</p>
              )}
              <div className="mt-2 flex items-center gap-1 text-xs font-medium text-emerald-700">
                <Database className="h-3 w-3" />
                Live MariaDB data
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="revenue">
        <TabsList>
          <TabsTrigger value="revenue">Revenue by Company</TabsTrigger>
          <TabsTrigger value="leads">Leads by Company</TabsTrigger>
          <TabsTrigger value="share">Revenue Share</TabsTrigger>
          <TabsTrigger value="trend">Revenue Trend</TabsTrigger>
        </TabsList>

        <TabsContent value="revenue" className="mt-4">
          <CompanyComparisonChart
            data={data?.charts.revenue_by_company ?? []}
            title="Monthly Revenue by Company"
            dataKey="revenue"
          />
        </TabsContent>

        <TabsContent value="leads" className="mt-4">
          <CompanyComparisonChart
            data={data?.charts.lead_comparison ?? []}
            title="Monthly Leads by Company"
            dataKey="leads"
          />
        </TabsContent>

        <TabsContent value="share" className="mt-4">
          <LeadSourcePieChart
            data={data?.charts.revenue_share ?? []}
            title="Revenue Share by Company"
          />
        </TabsContent>

        <TabsContent value="trend" className="mt-4">
          <RevenueTrendChart
            data={data?.charts.monthly_revenue_trend ?? []}
            title="Group Revenue Trend"
            color="#0F4C81"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
