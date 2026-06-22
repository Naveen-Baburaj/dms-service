'use client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency } from '@/lib/utils';
import type { CompanyChartData } from '@/types';

interface CompanyComparisonChartProps {
  data: CompanyChartData[];
  title?: string;
  dataKey?: 'revenue' | 'sales' | 'leads';
  className?: string;
}

const COMPANY_COLORS = { honda: '#E40521', nexa: '#1B4F8A', jaguar: '#555555' };

export function CompanyComparisonChart({
  data,
  title = 'Revenue by Company',
  dataKey = 'revenue',
  className,
}: CompanyComparisonChartProps) {
  const isRevenue = dataKey === 'revenue';
  const formatter = isRevenue
    ? (v: number) => `₹${(v / 100000).toFixed(0)}L`
    : (v: number) => v.toString();

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={formatter} />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', fontSize: '12px' }}
              formatter={(value: number, name: string) => [
                isRevenue ? formatCurrency(value) : value,
                name.charAt(0).toUpperCase() + name.slice(1),
              ]}
            />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '12px' }} />
            <Bar dataKey="honda" name="Honda" fill={COMPANY_COLORS.honda} radius={[4, 4, 0, 0]} maxBarSize={20} />
            <Bar dataKey="nexa" name="NEXA" fill={COMPANY_COLORS.nexa} radius={[4, 4, 0, 0]} maxBarSize={20} />
            <Bar dataKey="jaguar" name="Jaguar" fill={COMPANY_COLORS.jaguar} radius={[4, 4, 0, 0]} maxBarSize={20} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
