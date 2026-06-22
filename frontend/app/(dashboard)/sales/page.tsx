'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { salesApi } from '@/services/api/sales';
import { formatDate, formatCurrency } from '@/lib/utils';
import type { SalesFilter, SaleStatus } from '@/types';

const STATUS_VARIANTS: Record<SaleStatus, 'default' | 'success' | 'warning' | 'destructive' | 'secondary'> = {
  Draft: 'secondary',
  Confirmed: 'info' as 'default',
  Delivered: 'success',
  Cancelled: 'destructive',
};

export default function SalesPage() {
  const [filters, setFilters] = useState<SalesFilter>({ page: 1, page_size: 20 });

  const { data, isLoading } = useQuery({
    queryKey: ['sales', filters],
    queryFn: () => salesApi.getAll(filters),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sales</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{data?.total ?? 0} total sales</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Sale
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search sales..."
            className="pl-9"
            onChange={(e) =>
              setFilters((p) => ({ ...p, search: e.target.value || undefined, page: 1 }))
            }
          />
        </div>
      </div>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Invoice</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Vehicle / Model</TableHead>
              <TableHead>Final Price</TableHead>
              <TableHead>Payment Mode</TableHead>
              <TableHead>Delivery Date</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : (data?.data ?? []).map((sale) => (
                  <TableRow key={sale.id}>
                    <TableCell className="font-mono text-xs">{sale.invoice_no ?? sale.name}</TableCell>
                    <TableCell className="font-medium">{sale.customer_name}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium">{sale.model}</span>
                        <span className="text-xs text-muted-foreground">{sale.variant} · {sale.color}</span>
                      </div>
                    </TableCell>
                    <TableCell className="font-semibold">{formatCurrency(sale.final_price)}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">{sale.payment_mode}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {sale.delivery_date ? formatDate(sale.delivery_date) : '—'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[sale.status] ?? 'secondary'} className="text-xs">
                        {sale.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
