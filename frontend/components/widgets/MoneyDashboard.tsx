'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useMoneyWidget } from '@/hooks/useWidgets';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Minus,
  Briefcase,
  Youtube,
  Music2,
  LineChart,
  Loader2,
  AlertCircle,
} from 'lucide-react';

interface PortfolioItem {
  name: string;
  value: number;
  change: number;
  percentage: number;
}

interface IncomeStream {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  amount: number;
  percentage: number;
}

export function MoneyDashboard() {
  const { data, isLoading, error } = useMoneyWidget();

  // Mock data (used when backend returns not_connected or as fallback)
  const mockData = {
    netWorth: 47832,
    netWorthChange: 1204,
    netWorthChangePercent: 2.5,
    monthlyIncome: 4250,
    monthlyIncomeChange: 800,
    portfolio: [
      { name: 'Stocks', value: 28400, change: 3.2, percentage: 59.4 },
      { name: 'Crypto', value: 8200, change: -1.8, percentage: 17.1 },
      { name: 'Cash', value: 11232, change: 0, percentage: 23.5 },
    ],
    incomeStreams: [
      { name: 'Freelance', icon: Briefcase, amount: 2500, percentage: 58.8 },
      { name: 'YouTube', icon: Youtube, amount: 450, percentage: 10.6 },
      { name: 'TikTok', icon: Music2, amount: 120, percentage: 2.8 },
      { name: 'Dividends', icon: LineChart, amount: 180, percentage: 4.2 },
    ],
  };

  // Use API data if connected, otherwise use mock data
  const isConnected = data?.status === 'connected';
  const netWorth = isConnected && data?.summary?.net_worth ? data.summary.net_worth : mockData.netWorth;
  const netWorthChange = mockData.netWorthChange;
  const netWorthChangePercent = mockData.netWorthChangePercent;
  const monthlyIncome = isConnected && data?.summary?.monthly_income ? data.summary.monthly_income : mockData.monthlyIncome;
  const monthlyIncomeChange = mockData.monthlyIncomeChange;
  const portfolio = mockData.portfolio;
  const incomeStreams = mockData.incomeStreams;

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
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
              <Wallet className="h-4 w-4 text-emerald-400" />
            </div>
            <CardTitle className="text-sm font-semibold">MONEY DASHBOARD</CardTitle>
          </div>
          {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Connection Status Banner */}
        {data?.status === 'not_connected' && (
          <div className="flex items-center gap-2 p-2.5 rounded-lg border border-yellow-500/20 bg-yellow-500/5 text-xs">
            <AlertCircle className="h-3.5 w-3.5 text-yellow-400 flex-shrink-0" />
            <span className="text-yellow-300/80">
              {data.message || 'Connect your bank accounts to see real data'}
            </span>
          </div>
        )}

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

        {/* Footer note */}
        {!isConnected && (
          <p className="text-xs text-muted-foreground text-center pt-2 border-t border-white/5">
            Displaying mock data. Plaid integration coming soon.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
