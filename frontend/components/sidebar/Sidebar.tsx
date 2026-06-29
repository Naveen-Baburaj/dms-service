'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Users, UserCheck, ShoppingCart, CalendarCheck,
  Car, Wrench, FileText, BarChart3, Settings, Building2,
  UserCog, TrendingUp, Shield, ChevronLeft, ChevronRight, Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';
import { isGroupAdmin } from '@/types';
import { useState } from 'react';
import { Separator } from '@/components/ui/separator';

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const mainNavItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'AI Agents', href: '/chat', icon: Sparkles },
  { label: 'Leads', href: '/leads', icon: Users },
  { label: 'Customers', href: '/customers', icon: UserCheck },
  { label: 'Sales', href: '/sales', icon: ShoppingCart },
  { label: 'Bookings', href: '/bookings', icon: CalendarCheck },
  { label: 'Test Drives', href: '/test-drives', icon: Car },
  { label: 'Service', href: '/service', icon: Wrench },
  { label: 'Invoices', href: '/invoices', icon: FileText },
  { label: 'Reports', href: '/reports', icon: BarChart3 },
  { label: 'Settings', href: '/settings', icon: Settings },
];

const adminNavItems: NavItem[] = [
  { label: 'Companies', href: '/admin/companies', icon: Building2, adminOnly: true },
  { label: 'User Management', href: '/admin/users', icon: UserCog, adminOnly: true },
  { label: 'Analytics', href: '/admin/analytics', icon: TrendingUp, adminOnly: true },
  { label: 'System Settings', href: '/admin/system', icon: Shield, adminOnly: true },
];

const COMPANY_COLORS: Record<string, string> = {
  Honda: 'bg-honda',
  NEXA: 'bg-nexa',
  Jaguar: 'bg-jaguar',
  Group: 'bg-group',
};

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const [collapsed, setCollapsed] = useState(false);
  const showAdmin = user && isGroupAdmin(user.role);
  const companyColor = user ? COMPANY_COLORS[user.company] ?? 'bg-primary' : 'bg-primary';

  function getDashboardHref() {
    if (!user) return '/dashboard';
    const map: Record<string, string> = { Honda: '/honda', NEXA: '/nexa', Jaguar: '/jaguar', Group: '/admin' };
    return map[user.company] ?? '/dashboard';
  }

  const resolvedItems = mainNavItems.map((item) =>
    item.href === '/dashboard' ? { ...item, href: getDashboardHref() } : item,
  );

  return (
    <aside
      className={cn(
        'relative flex flex-col border-r border-border bg-card transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Logo area */}
      <div className={cn('flex items-center gap-3 p-4 border-b border-border', collapsed && 'justify-center')}>
        <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white font-bold text-sm', companyColor)}>
          {user?.company?.[0] ?? 'D'}
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate text-sm font-semibold">
                {showAdmin ? 'Admin' : user?.company ?? 'DMS'}
              </span>
              <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-violet-600">
                Demo
              </span>
            </div>
            <span className="truncate text-xs text-muted-foreground">DMS Demo</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2">
        <ul className="space-y-1">
          {resolvedItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            const isAI = item.href === '/chat';
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all',
                    isAI && !active
                      ? 'bg-gradient-to-r from-violet-500/10 to-indigo-500/10 text-violet-600 hover:from-violet-500/20 hover:to-indigo-500/20 border border-violet-500/20'
                      : active
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    collapsed && 'justify-center px-2',
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon className={cn('h-4 w-4 shrink-0', isAI && !active && 'text-violet-500')} />
                  {!collapsed && <span>{item.label}</span>}
                  {!collapsed && isAI && !active && (
                    <span className="ml-auto rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-violet-600">AI</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        {showAdmin && (
          <>
            <Separator className="my-4" />
            {!collapsed && (
              <p className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Administration
              </p>
            )}
            <ul className="space-y-1">
              {adminNavItems.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + '/');
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        active
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                        collapsed && 'justify-center px-2',
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-20 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background shadow-sm hover:bg-accent transition-colors"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>
    </aside>
  );
}
