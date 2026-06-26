'use client';
import { Bell, Search, LogOut, User, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { getInitials } from '@/lib/utils';
import type { CompanyType } from '@/types';

const COMPANY_LABELS: Record<string, string> = {
  Honda: 'Honda',
  NEXA: 'NEXA by Maruti',
  Jaguar: 'Jaguar Land Rover',
  Group: 'Group Admin',
};

function getCompanyColorHex(company: CompanyType): string {
  const colors: Record<CompanyType, string> = {
    Honda: '#E40521',
    NEXA: '#1B4F8A',
    Jaguar: '#1A1A1A',
    Group: '#0F4C81',
  };
  return colors[company];
}

export function Navbar() {
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');

  const companyLabel = user ? COMPANY_LABELS[user.company] ?? user.company : '';
  const companyColor = user ? getCompanyColorHex(user.company) : '#0F4C81';

  return (
    <header className="flex h-16 items-center gap-4 border-b border-border bg-background px-6">
      {/* Company branding */}
      <div className="flex items-center gap-2 min-w-0">
        <div
          className="h-2 w-2 rounded-full shrink-0"
          style={{ backgroundColor: companyColor }}
        />
        <span className="text-sm font-semibold text-foreground truncate hidden sm:block">
          {companyLabel}
        </span>
      </div>

      {/* Search */}
      <div className="flex-1 max-w-md mx-4 hidden md:block">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search leads, customers, vehicles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-muted/50 border-0 focus-visible:ring-1"
          />
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="hidden lg:flex flex-col items-end border-r border-border pr-3">
          <span className="text-sm font-semibold leading-none text-foreground">Genbyte.ai</span>
          <span className="mt-1 text-[10px] font-medium uppercase tracking-wider text-violet-500">AI Demo</span>
        </div>

        {/* Notifications */}
        <button className="relative flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-honda" />
          <span className="sr-only">Notifications</span>
        </button>

        {/* Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted transition-colors">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.avatar} />
                <AvatarFallback
                  className="text-white text-xs font-semibold"
                  style={{ backgroundColor: companyColor }}
                >
                  {user ? getInitials(user.full_name) : 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:flex flex-col items-start min-w-0">
                <span className="text-sm font-medium truncate max-w-[120px]">
                  {user?.full_name}
                </span>
                <span className="text-xs text-muted-foreground capitalize">
                  {user?.role.replace(/_/g, ' ')}
                </span>
              </div>
              <ChevronDown className="h-3 w-3 text-muted-foreground hidden sm:block" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="font-semibold">{user?.full_name}</span>
                <span className="text-xs text-muted-foreground font-normal">{user?.email}</span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={logout}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
