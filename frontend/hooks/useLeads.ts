'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { leadsApi } from '@/services/api/leads';
import type { LeadsFilter, CreateLeadDTO, UpdateLeadDTO } from '@/types';

const LEADS_KEY = 'leads';

export function useLeads(filters: LeadsFilter = {}) {
  return useQuery({
    queryKey: [LEADS_KEY, filters],
    queryFn: () => leadsApi.getAll(filters),
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: [LEADS_KEY, id],
    queryFn: () => leadsApi.getById(id),
    enabled: !!id,
  });
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateLeadDTO) => leadsApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: [LEADS_KEY] }),
  });
}

export function useUpdateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateLeadDTO) => leadsApi.update(payload),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: [LEADS_KEY] });
      qc.invalidateQueries({ queryKey: [LEADS_KEY, vars.id] });
    },
  });
}

export function useDeleteLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [LEADS_KEY] }),
  });
}
