'use client';
import { useState } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { LeadsTable } from '@/components/tables/LeadsTable';
import { useLeads, useDeleteLead } from '@/hooks/useLeads';
import { useToast } from '@/hooks/useToast';
import type { LeadsFilter, LeadStatus, Lead } from '@/types';

const LEAD_STATUSES: LeadStatus[] = [
  'New', 'Open', 'Replied', 'Opportunity', 'Quotation', 'Converted', 'Lost',
];

export default function LeadsPage() {
  const { toast } = useToast();
  const [filters, setFilters] = useState<LeadsFilter>({ page: 1, page_size: 20 });

  const { data, isLoading } = useLeads(filters);
  const deleteLead = useDeleteLead();

  function handlePageChange(page: number) {
    setFilters((prev) => ({ ...prev, page }));
  }

  function handleStatusFilter(status: string) {
    setFilters((prev) => ({
      ...prev,
      status: status === 'all' ? undefined : (status as LeadStatus),
      page: 1,
    }));
  }

  function handleSearch(value: string) {
    setFilters((prev) => ({ ...prev, search: value || undefined, page: 1 }));
  }

  function handleDelete(lead: Lead) {
    if (!confirm(`Delete lead "${lead.lead_name}"?`)) return;
    deleteLead.mutate(lead.id, {
      onSuccess: () => toast({ title: 'Lead deleted', variant: 'default' }),
      onError: () => toast({ title: 'Failed to delete lead', variant: 'destructive' }),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leads</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data?.total ?? 0} total leads
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Add Lead
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search leads..."
            className="pl-9"
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>
        <Select onValueChange={handleStatusFilter} defaultValue="all">
          <SelectTrigger className="w-44">
            <Filter className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {LEAD_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <LeadsTable
        leads={data?.data ?? []}
        total={data?.total ?? 0}
        page={filters.page ?? 1}
        pageSize={filters.page_size ?? 20}
        loading={isLoading}
        onPageChange={handlePageChange}
        onDelete={handleDelete}
        onView={(lead) => console.log('view', lead.id)}
        onEdit={(lead) => console.log('edit', lead.id)}
      />
    </div>
  );
}
