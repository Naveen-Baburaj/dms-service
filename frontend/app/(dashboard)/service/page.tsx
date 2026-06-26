'use client';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, Wrench } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { apiClient, unwrapFrappe } from '@/services/api/client';
import { formatCurrency } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  Open: 'bg-blue-100 text-blue-800 border-blue-200',
  'In Progress': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  Completed: 'bg-green-100 text-green-800 border-green-200',
  Invoiced: 'bg-purple-100 text-purple-800 border-purple-200',
  Cancelled: 'bg-red-100 text-red-800 border-red-200',
};

export default function ServicePage() {
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['service-jobs'],
    queryFn: async () => {
      const res = await apiClient.get('/method/dms.api.frontend_demo.records', {
        params: { resource: 'service_jobs', page: 1, page_size: 200 },
      });
      return unwrapFrappe<{ data: Record<string, unknown>[]; total: number }>(res.data);
    },
  });

  const jobs = (data?.data ?? []).filter(
    (j: { vehicle_reg_no?: string; service_type?: string }) =>
      !search ||
      j.vehicle_reg_no?.toLowerCase().includes(search.toLowerCase()) ||
      j.service_type?.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Service</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{data?.total ?? 0} service jobs</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Job Card
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by vehicle or service type..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Job No.</TableHead>
              <TableHead>Vehicle Reg.</TableHead>
              <TableHead>Service Type</TableHead>
              <TableHead>KM Reading</TableHead>
              <TableHead>Labour</TableHead>
              <TableHead>Parts</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : jobs.length === 0
              ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-16 text-muted-foreground">
                    <Wrench className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm">No service jobs found</p>
                  </TableCell>
                </TableRow>
              )
              : jobs.map((job: Record<string, unknown>) => (
                  <TableRow key={job.name as string}>
                    <TableCell className="font-mono text-xs">{job.name as string}</TableCell>
                    <TableCell className="font-medium">{job.vehicle_reg_no as string}</TableCell>
                    <TableCell>{job.service_type as string}</TableCell>
                    <TableCell>{job.km_reading ? `${job.km_reading} km` : '—'}</TableCell>
                    <TableCell>{formatCurrency(Number(job.labour_charges ?? 0))}</TableCell>
                    <TableCell>{formatCurrency(Number(job.parts_charges ?? 0))}</TableCell>
                    <TableCell className="font-semibold">{formatCurrency(Number(job.total_amount ?? 0))}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status as string] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                        {job.status as string}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
