'use client';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { KPIMetric } from '@/types';

interface KPICardProps {
  metric: KPIMetric;
  icon?: React.ElementType;
  iconColor?: string;
  className?: string;
  loading?: boolean;
}

export function KPICard({ metric, icon: Icon, iconColor = '#0F4C81', className, loading }: KPICardProps) {
  if (loading) {
    return (
      <Card className={cn('relative overflow-hidden', className)}>
        <CardContent className="p-5">
          <Skeleton className="h-4 w-24 mb-3" />
          <Skeleton className="h-8 w-32 mb-2" />
          <Skeleton className="h-4 w-20" />
        </CardContent>
      </Card>
    );
  }

  const isIncrease = metric.change_type === 'increase';
  const isDecrease = metric.change_type === 'decrease';
  const TrendIcon = isIncrease ? TrendingUp : isDecrease ? TrendingDown : Minus;
  const trendColor = isIncrease
    ? 'text-green-600'
    : isDecrease
      ? 'text-red-500'
      : 'text-muted-foreground';

  const displayValue =
    typeof metric.value === 'number'
      ? `${metric.prefix ?? ''}${metric.value.toLocaleString('en-IN')}${metric.suffix ?? ''}`
      : metric.value;

  return (
    <Card className={cn('relative overflow-hidden transition-shadow hover:shadow-md', className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-muted-foreground">{metric.label}</p>
          {Icon && (
            <div
              className="flex h-9 w-9 items-center justify-center rounded-lg opacity-90"
              style={{ backgroundColor: `${iconColor}15` }}
            >
              <Icon className="h-4 w-4" style={{ color: iconColor }} />
            </div>
          )}
        </div>
        <div className="mt-2">
          <p className="text-2xl font-bold tracking-tight">{displayValue}</p>
          <div className={cn('mt-1 flex items-center gap-1 text-xs font-medium', trendColor)}>
            <TrendIcon className="h-3 w-3" />
            <span>
              {Math.abs(metric.change)}% vs last month
            </span>
          </div>
        </div>
        {/* Subtle accent line */}
        <div
          className="absolute bottom-0 left-0 h-0.5 w-full"
          style={{ backgroundColor: iconColor, opacity: 0.4 }}
        />
      </CardContent>
    </Card>
  );
}

export function KPICardGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4', className)}>
      {children}
    </div>
  );
}
