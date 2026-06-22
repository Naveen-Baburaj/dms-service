'use client';
import { Building2, TrendingUp, Users, Car } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

const COMPANIES = [
  {
    id: 'HONDA-00001',
    name: 'Honda',
    brand: 'Honda',
    type: 'Dealership',
    color: 'bg-red-500',
    users: 12,
    vehicles: 48,
    leads: 134,
    isActive: true,
  },
  {
    id: 'NEXA-00001',
    name: 'NEXA',
    brand: 'NEXA (Maruti)',
    type: 'Dealership',
    color: 'bg-blue-600',
    users: 9,
    vehicles: 35,
    leads: 98,
    isActive: true,
  },
  {
    id: 'JAG-00001',
    name: 'Jaguar',
    brand: 'Jaguar Land Rover',
    type: 'Luxury Dealership',
    color: 'bg-gray-800',
    users: 6,
    vehicles: 22,
    leads: 41,
    isActive: true,
  },
];

export default function CompaniesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Companies</h1>
        <p className="text-muted-foreground text-sm mt-0.5">Manage all dealership companies in the group</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {COMPANIES.map((c) => (
          <Card key={c.id} className="relative overflow-hidden">
            <div className={`absolute top-0 left-0 right-0 h-1 ${c.color}`} />
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`h-10 w-10 rounded-lg ${c.color} flex items-center justify-center text-white font-bold`}>
                    {c.name[0]}
                  </div>
                  <div>
                    <CardTitle className="text-base">{c.name}</CardTitle>
                    <p className="text-xs text-muted-foreground">{c.brand}</p>
                  </div>
                </div>
                <Badge variant={c.isActive ? 'success' : 'secondary'} className="text-xs">
                  {c.isActive ? 'Active' : 'Inactive'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-muted/50 py-2 px-1">
                  <Users className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-lg font-bold">{c.users}</p>
                  <p className="text-xs text-muted-foreground">Users</p>
                </div>
                <div className="rounded-lg bg-muted/50 py-2 px-1">
                  <Car className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-lg font-bold">{c.vehicles}</p>
                  <p className="text-xs text-muted-foreground">Vehicles</p>
                </div>
                <div className="rounded-lg bg-muted/50 py-2 px-1">
                  <TrendingUp className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-lg font-bold">{c.leads}</p>
                  <p className="text-xs text-muted-foreground">Leads</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-3 text-center">{c.type} · {c.id}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Company ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Brand</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Users</TableHead>
              <TableHead>Vehicles</TableHead>
              <TableHead>Active Leads</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {COMPANIES.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-mono text-xs">{c.id}</TableCell>
                <TableCell className="font-medium">{c.name}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{c.brand}</TableCell>
                <TableCell className="text-sm">{c.type}</TableCell>
                <TableCell>{c.users}</TableCell>
                <TableCell>{c.vehicles}</TableCell>
                <TableCell>{c.leads}</TableCell>
                <TableCell>
                  <Badge variant="success" className="text-xs">Active</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
