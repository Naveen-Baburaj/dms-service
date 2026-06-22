'use client';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, Car } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { salesApi } from '@/services/api/sales';
import { formatDate } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  Scheduled: 'bg-blue-100 text-blue-800 border-blue-200',
  Completed: 'bg-green-100 text-green-800 border-green-200',
  Cancelled: 'bg-red-100 text-red-800 border-red-200',
  'No Show': 'bg-gray-100 text-gray-700 border-gray-200',
};

export default function TestDrivesPage() {
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['test-drives'],
    queryFn: () => salesApi.getTestDrives(),
  });

  const filtered = (data?.data ?? []).filter(
    (td) =>
      !search ||
      td.contact_name?.toLowerCase().includes(search.toLowerCase()) ||
      td.model?.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Test Drives</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data?.total ?? 0} total test drives
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Schedule Test Drive
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search test drives..."
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
              <TableHead>ID</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Vehicle</TableHead>
              <TableHead>Scheduled Date</TableHead>
              <TableHead>Time</TableHead>
              <TableHead>Rating</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : filtered.length === 0
              ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-16 text-muted-foreground">
                    <Car className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm">No test drives scheduled</p>
                  </TableCell>
                </TableRow>
              )
              : filtered.map((td) => (
                  <TableRow key={td.id}>
                    <TableCell className="font-mono text-xs">{td.id}</TableCell>
                    <TableCell className="font-medium">{td.contact_name}</TableCell>
                    <TableCell>{td.model ?? '—'}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {td.scheduled_date ? formatDate(td.scheduled_date) : '—'}
                    </TableCell>
                    <TableCell className="text-sm">{td.scheduled_time ?? '—'}</TableCell>
                    <TableCell>
                      {td.rating ? (
                        <span className="flex items-center gap-1 text-sm font-medium">
                          <span className="text-yellow-500">★</span> {td.rating}/5
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[td.status] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                        {td.status}
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
