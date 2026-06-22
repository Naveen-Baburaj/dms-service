'use client';
import { Download, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuthStore } from '@/store/authStore';
import { isGroupAdmin } from '@/types';
import { useHondaDashboard, useGroupDashboard } from '@/hooks/useDashboard';
import { SalesTrendChart } from '@/components/charts/SalesTrendChart';
import { RevenueTrendChart } from '@/components/charts/RevenueTrendChart';
import { CompanyComparisonChart } from '@/components/charts/CompanyComparisonChart';

export default function ReportsPage() {
  const { user } = useAuthStore();
  const showGroupReports = user && isGroupAdmin(user.role);

  const { data: hondaData } = useHondaDashboard();
  const { data: groupData } = useGroupDashboard();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Performance analytics and business intelligence
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Calendar className="mr-2 h-4 w-4" />
            Date Range
          </Button>
          <Button size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      <Tabs defaultValue="sales">
        <TabsList>
          <TabsTrigger value="sales">Sales</TabsTrigger>
          <TabsTrigger value="revenue">Revenue</TabsTrigger>
          <TabsTrigger value="leads">Leads</TabsTrigger>
          {showGroupReports && <TabsTrigger value="group">Group</TabsTrigger>}
        </TabsList>

        <TabsContent value="sales" className="space-y-4 mt-4">
          <SalesTrendChart
            data={hondaData?.charts.monthly_sales_trend ?? []}
            title="Sales Trend (This Year)"
          />
        </TabsContent>

        <TabsContent value="revenue" className="space-y-4 mt-4">
          <RevenueTrendChart
            data={hondaData?.charts.revenue_trend ?? []}
            title="Revenue Trend (This Year)"
          />
        </TabsContent>

        <TabsContent value="leads" className="space-y-4 mt-4">
          <SalesTrendChart
            data={hondaData?.charts.sales_conversion ?? []}
            title="Lead Conversion Trend"
            color="#10B981"
          />
        </TabsContent>

        {showGroupReports && (
          <TabsContent value="group" className="space-y-4 mt-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <CompanyComparisonChart
                data={groupData?.charts.revenue_by_company ?? []}
                title="Revenue by Company"
                dataKey="revenue"
              />
              <CompanyComparisonChart
                data={groupData?.charts.lead_comparison ?? []}
                title="Leads by Company"
                dataKey="leads"
              />
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
