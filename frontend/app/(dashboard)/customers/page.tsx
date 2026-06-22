'use client';
import { useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { customersApi } from '@/services/api/customers';
import { formatDate, formatCurrency } from '@/lib/utils';
import type { CustomersFilter } from '@/types';

export default function CustomersPage() {
  const [filters, setFilters] = useState<CustomersFilter>({ page: 1, page_size: 20 });

  const { data, isLoading } = useQuery({
    queryKey: ['customers', filters],
    queryFn: () => customersApi.getAll(filters),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Customers</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{data?.total ?? 0} total customers</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Add Customer
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search customers..."
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
              <TableHead>Name</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Total Purchases</TableHead>
              <TableHead>Last Purchase</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : (data?.data ?? []).map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell className="font-medium">{customer.customer_name}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm">{customer.mobile_no}</span>
                        <span className="text-xs text-muted-foreground">{customer.email}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">{customer.customer_type}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">{formatCurrency(customer.total_purchases)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {customer.last_purchase_date ? formatDate(customer.last_purchase_date) : '—'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={customer.status === 'Active' ? 'success' : 'secondary'} className="text-xs">
                        {customer.status}
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
