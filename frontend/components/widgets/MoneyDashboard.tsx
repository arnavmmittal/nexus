'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Minus,
  Briefcase,
  Youtube,
  Music2,
  LineChart,
} from 'lucide-react';

interface PortfolioItem {
  name: string;
  value: number;
  change: number;
  percentage: number;
}

interface IncomeStream {
  name: string;
  icon: React.ElementType;
  amount: number;
  percentage: number;
}

export function MoneyDashboard() {
  // Mock data
  const netWorth = 47832;
  const netWorthChange = 1204;
  const netWorthChangePercent = 2.5;

  const monthlyIncome = 4250;
  const monthlyIncomeChange = 800;

  const portfolio: PortfolioItem[] = [
    { name: 'Stocks', value: 28400, change: 3.2, percentage: 59.4 },
    { name: 'Crypto', value: 8200, change: -1.8, percentage: 17.1 },
    { name: 'Cash', value: 11232, change: 0, percentage: 23.5 },
  ];

  const incomeStreams: IncomeStream[] = [
    { name: 'Freelance', icon: Briefcase, amount: 2500, percentage: 58.8 },
    { name: 'YouTube', icon: Youtube, amount: 450, percentage: 10.6 },
    { name: 'TikTok', icon: Music2, amount: 120, percentage: 2.8 },
    { name: 'Dividends', icon: LineChart, amount: 180, percentage: 4.2 },
  ];

  const formatMoney = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getChangeIcon = (change: number) => {
    if (change > 0) return <TrendingUp className="h-3 w-3" />;
    if (change < 0) return <TrendingDown className="h-3 w-3" />;
    return <Minus className="h-3 w-3" />;
  };

  const getChangeColor = (change: number) => {
    if (change > 0) return 'text-emerald-400';
    if (change < 0) return 'text-red-400';
    return 'text-muted-foreground';
  };

  return (
    <Card className="glass-panel-hover border-emerald-500/20 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
            <Wallet className="h-4 w-4 text-emerald-400" />
          </div>
          <CardTitle className="text-sm font-semibold">MONEY DASHBOARD</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Net Worth & Monthly Income */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Net Worth</p>
            <p className="stat-number text-2xl font-bold text-emerald-300">{formatMoney(netWorth)}</p>
            <div className={cn('flex items-center gap-1 text-xs mt-1', getChangeColor(netWorthChange))}>
              {getChangeIcon(netWorthChange)}
              <span className="stat-number">{formatMoney(netWorthChange)}</span>
              <span className="stat-number">({netWorthChangePercent}%)</span>
              <span className="text-muted-foreground">this month</span>
            </div>
          </div>
          <div className="p-4 rounded-xl border border-white/5 bg-white/[0.02]">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Monthly Income</p>
            <p className="stat-number text-2xl font-bold">{formatMoney(monthlyIncome)}</p>
            <div className={cn('flex items-center gap-1 text-xs mt-1', getChangeColor(monthlyIncomeChange))}>
              {getChangeIcon(monthlyIncomeChange)}
              <span className="stat-number">{formatMoney(monthlyIncomeChange)}</span>
              <span className="text-muted-foreground">vs last mo</span>
            </div>
          </div>
        </div>

        {/* Portfolio Breakdown */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Portfolio</p>
          <div className="space-y-2">
            {portfolio.map((item) => (
              <div key={item.name} className="flex items-center gap-3">
                <span className="text-sm w-16">{item.name}</span>
                <span className="stat-number text-sm w-20">{formatMoney(item.value)}</span>
                <div className="flex-1">
                  <Progress
                    value={item.percentage}
                    className="h-2"
                  />
                </div>
                <div className={cn('flex items-center gap-1 text-xs w-16 justify-end', getChangeColor(item.change))}>
                  {getChangeIcon(item.change)}
                  <span className="stat-number">{Math.abs(item.change)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Income Streams */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Income Streams</p>
          <div className="space-y-2">
            {incomeStreams.map((stream) => {
              const Icon = stream.icon;
              return (
                <div key={stream.name} className="flex items-center gap-3">
                  <div className="flex items-center gap-2 w-28">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{stream.name}</span>
                  </div>
                  <span className="stat-number text-sm text-emerald-400 w-16">{formatMoney(stream.amount)}</span>
                  <div className="flex-1">
                    <Progress
                      value={stream.percentage}
                      className="h-1.5 bg-emerald-950"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
