'use client';
import { useState } from 'react';
import { Eye, Edit, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDate, timeAgo } from '@/lib/utils';
import { cn } from '@/lib/utils';
import type { Lead, LeadStatus } from '@/types';

const STATUS_VARIANTS: Record<LeadStatus, 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'secondary'> = {
  New: 'info',
  Open: 'default',
  Replied: 'secondary',
  Opportunity: 'warning',
  Quotation: 'warning',
  Converted: 'success',
  'Do Not Contact': 'destructive',
  Lost: 'destructive',
};

interface LeadsTableProps {
  leads: Lead[];
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  onPageChange: (page: number) => void;
  onEdit?: (lead: Lead) => void;
  onDelete?: (lead: Lead) => void;
  onView?: (lead: Lead) => void;
}

export function LeadsTable({
  leads,
  total,
  page,
  pageSize,
  loading,
  onPageChange,
  onEdit,
  onDelete,
  onView,
}: LeadsTableProps) {
  const totalPages = Math.ceil(total / pageSize);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Name</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Vehicle Interest</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                  No leads found
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow key={lead.id} className="hover:bg-muted/30">
                  <TableCell className="font-medium">{lead.lead_name}</TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm">{lead.mobile_no}</span>
                      <span className="text-xs text-muted-foreground">{lead.email}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[lead.status] ?? 'secondary'} className="text-xs">
                      {lead.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{lead.source}</TableCell>
                  <TableCell className="text-sm">{lead.vehicle_interest ?? '—'}</TableCell>
                  <TableCell className="text-sm text-muted-foreground" title={formatDate(lead.created_at)}>
                    {timeAgo(lead.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      {onView && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onView(lead)}>
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {onEdit && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(lead)}>
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {onDelete && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => onDelete(lead)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              disabled={page === 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="px-2">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              disabled={page === totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
