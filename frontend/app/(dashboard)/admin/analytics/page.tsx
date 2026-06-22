'use client';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const groupRevenue = MONTHS.map((month, i) => ({
  month,
  Honda: 18 + Math.round(Math.sin(i * 0.6) * 4 + Math.random() * 3),
  NEXA: 14 + Math.round(Math.sin(i * 0.5 + 1) * 3 + Math.random() * 2),
  Jaguar: 9 + Math.round(Math.sin(i * 0.4 + 2) * 2 + Math.random() * 2),
}));

const leadFunnel = [
  { name: 'Inquiries', value: 420 },
  { name: 'Qualified', value: 280 },
  { name: 'Test Drive', value: 160 },
  { name: 'Negotiation', value: 95 },
  { name: 'Converted', value: 62 },
];

const marketShare = [
  { name: 'Honda', value: 47, color: '#E40521' },
  { name: 'NEXA', value: 34, color: '#1B4F8A' },
  { name: 'Jaguar', value: 19, color: '#1A1A1A' },
];

const conversionTrend = MONTHS.map((month, i) => ({
  month,
  rate: +(13 + Math.sin(i * 0.7) * 2.5 + Math.random()).toFixed(1),
}));

const KPI = [
  { label: 'Group Revenue', value: '₹41.2L', change: +8.3, period: 'vs last month' },
  { label: 'Total Leads', value: '420', change: +12.1, period: 'vs last month' },
  { label: 'Avg Conversion', value: '14.8%', change: +1.2, period: 'vs last month' },
  { label: 'Vehicles Sold', value: '62', change: -3.4, period: 'vs last month' },
];

export default function GroupAnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Group Analytics</h1>
        <p className="text-muted-foreground text-sm mt-0.5">Consolidated performance across Honda, NEXA, and Jaguar</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {KPI.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-5">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{kpi.label}</p>
              <p className="text-2xl font-bold mt-1">{kpi.value}</p>
              <div className={`flex items-center gap-1 mt-1 text-xs font-medium ${kpi.change > 0 ? 'text-emerald-600' : kpi.change < 0 ? 'text-red-500' : 'text-muted-foreground'}`}>
                {kpi.change > 0 ? <TrendingUp className="h-3 w-3" /> : kpi.change < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                {kpi.change > 0 ? '+' : ''}{kpi.change}% {kpi.period}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="revenue">
        <TabsList>
          <TabsTrigger value="revenue">Revenue by Company</TabsTrigger>
          <TabsTrigger value="leads">Lead Funnel</TabsTrigger>
          <TabsTrigger value="share">Market Share</TabsTrigger>
          <TabsTrigger value="conversion">Conversion Trend</TabsTrigger>
        </TabsList>

        <TabsContent value="revenue">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Monthly Revenue by Company (₹ Lakhs)</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={groupRevenue} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number) => `₹${v}L`} />
                  <Legend />
                  <Bar dataKey="Honda" fill="#E40521" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="NEXA" fill="#1B4F8A" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Jaguar" fill="#1A1A1A" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="leads">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Lead Conversion Funnel (YTD)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-w-md">
                {leadFunnel.map((stage, i) => (
                  <div key={stage.name} className="flex items-center gap-3">
                    <div className="w-24 text-sm text-muted-foreground shrink-0">{stage.name}</div>
                    <div className="flex-1 bg-muted rounded-full h-7 overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full flex items-center justify-end pr-3 transition-all"
                        style={{ width: `${(stage.value / leadFunnel[0].value) * 100}%` }}
                      >
                        <span className="text-xs text-white font-semibold">{stage.value}</span>
                      </div>
                    </div>
                    <div className="w-12 text-xs text-right text-muted-foreground">
                      {i === 0 ? '100%' : `${Math.round((stage.value / leadFunnel[0].value) * 100)}%`}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="share">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Revenue Market Share</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-10">
              <ResponsiveContainer width={280} height={280}>
                <PieChart>
                  <Pie data={marketShare} dataKey="value" cx="50%" cy="50%" outerRadius={110} label={({ name, value }) => `${name} ${value}%`} labelLine={false}>
                    {marketShare.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => `${v}%`} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-3">
                {marketShare.map((item) => (
                  <div key={item.name} className="flex items-center gap-3">
                    <span className="h-3 w-3 rounded-full shrink-0" style={{ background: item.color }} />
                    <span className="text-sm font-medium w-16">{item.name}</span>
                    <span className="text-sm font-bold">{item.value}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="conversion">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Group Conversion Rate Trend (%)</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={conversionTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="convGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis domain={[10, 20]} tick={{ fontSize: 12 }} unit="%" />
                  <Tooltip formatter={(v: number) => `${v}%`} />
                  <Area type="monotone" dataKey="rate" stroke="#6366f1" fill="url(#convGrad)" strokeWidth={2} dot={{ r: 3 }} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
