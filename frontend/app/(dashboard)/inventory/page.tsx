'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Car, RefreshCw, Search } from 'lucide-react';

import {
  getVehicleInventory,
  type VehicleInventoryResponse,
  type VehicleInventoryRow,
} from '@/services/api/inventory';

function money(value: number | null | undefined): string {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount) || amount <= 0) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
}

function statusClass(status: string): string {
  const value = status.toLowerCase();
  if (value === 'in stock') {
    return 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20';
  }
  if (value === 'booked') {
    return 'bg-blue-500/10 text-blue-700 border-blue-500/20';
  }
  if (value === 'transit') {
    return 'bg-amber-500/10 text-amber-700 border-amber-500/20';
  }
  return 'bg-slate-500/10 text-slate-700 border-slate-500/20';
}

export default function InventoryPage() {
  const [inventory, setInventory] =
    useState<VehicleInventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [company, setCompany] = useState('All');
  const [status, setStatus] = useState('All');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getVehicleInventory();
      setInventory(result);
      if (!result.is_group_admin) {
        setCompany(result.scope_label);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load vehicle inventory.',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = inventory?.rows ?? [];
  const companies = Object.keys(inventory?.company_counts ?? {});
  const statuses = ['In Stock', 'Booked', 'Transit', 'Sold'];

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();

    return rows.filter((row) => {
      if (company !== 'All' && row.company_name !== company) {
        return false;
      }
      if (status !== 'All' && row.stock_status !== status) {
        return false;
      }
      if (!query) return true;

      return [
        row.vehicle_name,
        row.model,
        row.variant,
        row.color,
        row.fuel_type,
        row.transmission,
        row.chassis_no,
        row.company_name,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(query),
        );
    });
  }, [rows, company, status, search]);

  const cards = [
    { label: 'Total Vehicles', value: inventory?.total ?? 0 },
    {
      label: 'In Stock',
      value: inventory?.status_counts?.['In Stock'] ?? 0,
    },
    {
      label: 'Booked',
      value: inventory?.status_counts?.Booked ?? 0,
    },
    {
      label: 'In Transit',
      value: inventory?.status_counts?.Transit ?? 0,
    },
    {
      label: 'Sold',
      value: inventory?.status_counts?.Sold ?? 0,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Car className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">
              Vehicle Inventory
            </h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {inventory
              ? `${inventory.scope_label} · Live data from ${inventory.data_source}`
              : 'Live dealership stock from Frappe'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium hover:bg-accent disabled:opacity-60"
        >
          <RefreshCw
            className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`}
          />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-border bg-card p-4 shadow-sm"
          >
            <p className="text-xs font-medium text-muted-foreground">
              {card.label}
            </p>
            <p className="mt-2 text-2xl font-bold">
              {loading ? '—' : card.value.toLocaleString('en-IN')}
            </p>
          </div>
        ))}
      </div>

      {inventory?.is_group_admin && companies.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {companies.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() =>
                setCompany(company === name ? 'All' : name)
              }
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                company === name
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background hover:bg-accent'
              }`}
            >
              {name}: {inventory.company_counts[name]}
            </button>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex flex-wrap gap-3 border-b border-border p-4">
          <div className="relative min-w-[240px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search model, variant, colour, fuel, chassis..."
              className="h-10 w-full rounded-lg border border-border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          {inventory?.is_group_admin && (
            <select
              value={company}
              onChange={(event) => setCompany(event.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm"
            >
              <option value="All">All companies</option>
              {companies.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          )}

          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm"
          >
            <option value="All">All stock statuses</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-auto">
          <table className="w-full min-w-[1180px] text-sm">
            <thead className="bg-muted/40">
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left font-semibold">
                  Company
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Vehicle
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Model
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Variant
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Colour
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Year
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Fuel
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Transmission
                </th>
                <th className="px-4 py-3 text-left font-semibold">
                  Stock Status
                </th>
                <th className="px-4 py-3 text-right font-semibold">
                  On-Road Price
                </th>
              </tr>
            </thead>
            <tbody>
              {!loading && filteredRows.length === 0 && (
                <tr>
                  <td
                    colSpan={10}
                    className="px-4 py-12 text-center text-muted-foreground"
                  >
                    No vehicles match the selected filters.
                  </td>
                </tr>
              )}

              {filteredRows.map((row: VehicleInventoryRow) => {
                const stockStatus = row.stock_status ?? 'Unknown';
                return (
                  <tr
                    key={row.name}
                    className="border-b border-border/60 last:border-0 hover:bg-muted/25"
                  >
                    <td className="px-4 py-3 font-medium">
                      {row.company_name}
                    </td>
                    <td className="px-4 py-3">
                      {row.vehicle_name || '—'}
                    </td>
                    <td className="px-4 py-3">{row.model}</td>
                    <td className="px-4 py-3">{row.variant}</td>
                    <td className="px-4 py-3">{row.color}</td>
                    <td className="px-4 py-3">{row.year ?? '—'}</td>
                    <td className="px-4 py-3">
                      {row.fuel_type || '—'}
                    </td>
                    <td className="px-4 py-3">
                      {row.transmission || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClass(stockStatus)}`}
                      >
                        {stockStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {money(row.on_road_price)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
          Showing {filteredRows.length.toLocaleString('en-IN')} of{' '}
          {(inventory?.total ?? 0).toLocaleString('en-IN')} authorised
          vehicle record(s).
        </div>
      </div>
    </div>
  );
}
