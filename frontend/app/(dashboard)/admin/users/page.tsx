'use client';
import { useState } from 'react';
import { Search, UserPlus, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

const MOCK_USERS = [
  { id: 'u1', name: 'Rahul Sharma', email: 'honda.manager@dms.local', role: 'Honda Manager', company: 'Honda', companyColor: 'bg-red-500', lastLogin: '2 hours ago', isActive: true },
  { id: 'u2', name: 'Sunita Rao', email: 'honda.user@dms.local', role: 'Honda User', company: 'Honda', companyColor: 'bg-red-500', lastLogin: '1 day ago', isActive: true },
  { id: 'u3', name: 'Priya Mehta', email: 'nexa.manager@dms.local', role: 'NEXA Manager', company: 'NEXA', companyColor: 'bg-blue-600', lastLogin: '30 min ago', isActive: true },
  { id: 'u4', name: 'Vikram Singh', email: 'nexa.user@dms.local', role: 'NEXA User', company: 'NEXA', companyColor: 'bg-blue-600', lastLogin: '3 days ago', isActive: true },
  { id: 'u5', name: 'Arjun Kapoor', email: 'jaguar.manager@dms.local', role: 'Jaguar Manager', company: 'Jaguar', companyColor: 'bg-gray-800', lastLogin: 'Today', isActive: true },
  { id: 'u6', name: 'Nisha Patel', email: 'jaguar.user@dms.local', role: 'Jaguar User', company: 'Jaguar', companyColor: 'bg-gray-800', lastLogin: '5 days ago', isActive: false },
  { id: 'u7', name: 'Admin User', email: 'admin@dms.local', role: 'Group Admin', company: 'Group', companyColor: 'bg-indigo-600', lastLogin: 'Just now', isActive: true },
];

const ROLE_COLORS: Record<string, string> = {
  'Honda Manager': 'bg-red-100 text-red-800 border-red-200',
  'Honda User': 'bg-red-50 text-red-700 border-red-100',
  'NEXA Manager': 'bg-blue-100 text-blue-800 border-blue-200',
  'NEXA User': 'bg-blue-50 text-blue-700 border-blue-100',
  'Jaguar Manager': 'bg-gray-100 text-gray-800 border-gray-300',
  'Jaguar User': 'bg-gray-50 text-gray-700 border-gray-200',
  'Group Admin': 'bg-indigo-100 text-indigo-800 border-indigo-200',
};

export default function UserManagementPage() {
  const [search, setSearch] = useState('');

  const filtered = MOCK_USERS.filter(
    (u) =>
      !search ||
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.role.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">User Management</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{MOCK_USERS.length} users across all companies</p>
        </div>
        <Button>
          <UserPlus className="mr-2 h-4 w-4" />
          Add User
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search users..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Last Login</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className={`${u.companyColor} text-white text-xs font-semibold`}>
                        {u.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="text-sm font-medium">{u.name}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${ROLE_COLORS[u.role] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                    {u.role === 'Group Admin' && <Shield className="h-3 w-3" />}
                    {u.role}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${u.companyColor}`} />
                    <span className="text-sm">{u.company}</span>
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{u.lastLogin}</TableCell>
                <TableCell>
                  <Badge variant={u.isActive ? 'success' : 'secondary'} className="text-xs">
                    {u.isActive ? 'Active' : 'Inactive'}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" className="text-xs">Edit</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
