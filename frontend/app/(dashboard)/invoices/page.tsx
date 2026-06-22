'use client';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, FileText, Download } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { apiClient } from '@/services/api/client';
import { formatCurrency, formatDate } from '@/lib/utils';

const PAYMENT_COLORS: Record<string, string> = {
  Unpaid: 'bg-red-100 text-red-800 border-red-200',
  Partial: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  Paid: 'bg-green-100 text-green-800 border-green-200',
  Overdue: 'bg-orange-100 text-orange-800 border-orange-200',
};

export default function InvoicesPage() {
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['invoices'],
    queryFn: async () => {
      const res = await apiClient.get('/api/method/dms.api.invoices.get_invoices');
      return res.data?.data ?? { data: [], total: 0 };
    },
  });

  const invoices = (data?.data ?? []).filter(
    (inv: { customer_name?: string; invoice_no?: string }) =>
      !search ||
      inv.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
      inv.invoice_no?.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Invoices</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{data?.total ?? 0} total invoices</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Invoice
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search invoices..."
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
              <TableHead>Invoice No.</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Subtotal</TableHead>
              <TableHead>Tax</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Payment Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
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
              : invoices.length === 0
              ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-16 text-muted-foreground">
                    <FileText className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm">No invoices found</p>
                  </TableCell>
                </TableRow>
              )
              : invoices.map((inv: Record<string, unknown>) => (
                  <TableRow key={inv.name as string}>
                    <TableCell className="font-mono text-xs font-medium">{inv.name as string}</TableCell>
                    <TableCell className="font-medium">{inv.customer_name as string ?? '—'}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{inv.invoice_type as string}</TableCell>
                    <TableCell>{formatCurrency(Number(inv.subtotal ?? 0))}</TableCell>
                    <TableCell className="text-muted-foreground">{formatCurrency(Number(inv.tax_amount ?? 0))}</TableCell>
                    <TableCell className="font-semibold">{formatCurrency(Number(inv.total_amount ?? 0))}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${PAYMENT_COLORS[inv.payment_status as string] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                        {inv.payment_status as string}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm">
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
