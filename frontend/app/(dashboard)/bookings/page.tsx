'use client';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, Calendar } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { salesApi } from '@/services/api/sales';
import { formatDate, formatCurrency } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  Pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  Confirmed: 'bg-blue-100 text-blue-800 border-blue-200',
  Delivered: 'bg-green-100 text-green-800 border-green-200',
  Cancelled: 'bg-red-100 text-red-800 border-red-200',
};

export default function BookingsPage() {
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['bookings'],
    queryFn: () => salesApi.getBookings(),
  });

  const filtered = (data?.data ?? []).filter(
    (b) =>
      !search ||
      b.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
      b.model?.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bookings</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data?.total ?? 0} total bookings
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Booking
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search bookings..."
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
              <TableHead>Booking ID</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Vehicle</TableHead>
              <TableHead>Booking Amount</TableHead>
              <TableHead>Booking Date</TableHead>
              <TableHead>Expected Delivery</TableHead>
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
                    <Calendar className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm">No bookings found</p>
                  </TableCell>
                </TableRow>
              )
              : filtered.map((booking) => (
                  <TableRow key={booking.id}>
                    <TableCell className="font-mono text-xs">{booking.id}</TableCell>
                    <TableCell className="font-medium">{booking.customer_name}</TableCell>
                    <TableCell>{booking.model ? `${booking.model} ${booking.variant ?? ''}`.trim() : '—'}</TableCell>
                    <TableCell className="font-semibold">{formatCurrency(booking.booking_amount)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {booking.booking_date ? formatDate(booking.booking_date) : '—'}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {booking.expected_delivery ? formatDate(booking.expected_delivery) : '—'}
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[booking.status] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                        {booking.status}
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
