'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Heart,
  Moon,
  Zap,
  Dumbbell,
  TrendingUp,
  Lightbulb,
  Check,
  Minus,
} from 'lucide-react';

interface DayData {
  day: string;
  sleep: number;
  gym: boolean | null;
  steps: string;
}

export function HealthSnapshot() {
  // Mock data
  const sleep = {
    hours: 7.2,
    score: 82,
  };

  const energy = {
    level: 4, // out of 5
    label: 'High',
  };

  const workout = {
    completed: true,
    type: 'Push Day',
  };

  const weeklyData: DayData[] = [
    { day: 'M', sleep: 7.5, gym: true, steps: '8k' },
    { day: 'T', sleep: 8.2, gym: false, steps: '12k' },
    { day: 'W', sleep: 6.8, gym: true, steps: '6k' },
    { day: 'T', sleep: 7.0, gym: false, steps: '9k' },
    { day: 'F', sleep: 0, gym: null, steps: '--' },
    { day: 'S', sleep: 0, gym: null, steps: '--' },
    { day: 'S', sleep: 0, gym: null, steps: '--' },
  ];

  const trend = {
    metric: 'Sleep quality',
    change: 12,
    direction: 'up',
    period: 'vs last week',
  };

  const insight = {
    text: 'Best energy on days after 7+ hour sleep',
  };

  const getSleepBarHeight = (hours: number) => {
    if (hours === 0) return 0;
    return Math.min((hours / 9) * 100, 100);
  };

  return (
    <Card className="glass-panel-hover border-orange-500/20 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500/10">
            <Heart className="h-4 w-4 text-orange-400" />
          </div>
          <CardTitle className="text-sm font-semibold">HEALTH SNAPSHOT</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Today's Stats */}
        <div className="grid grid-cols-3 gap-3">
          {/* Sleep */}
          <div className="p-3 rounded-xl border border-white/5 bg-white/[0.02] text-center">
            <Moon className="h-4 w-4 text-blue-400 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Sleep</p>
            <p className="stat-number text-xl font-bold">{sleep.hours}h</p>
            <div className="flex items-center justify-center gap-1 mt-1">
              <span className="text-yellow-400">★</span>
              <span className="stat-number text-xs text-muted-foreground">{sleep.score}/100</span>
            </div>
          </div>

          {/* Energy */}
          <div className="p-3 rounded-xl border border-white/5 bg-white/[0.02] text-center">
            <Zap className="h-4 w-4 text-yellow-400 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Energy</p>
            <div className="flex justify-center gap-0.5 my-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className={cn(
                    'w-3 h-5 rounded-sm',
                    i <= energy.level ? 'bg-yellow-400' : 'bg-white/10'
                  )}
                />
              ))}
            </div>
            <p className="text-xs font-medium text-yellow-300">{energy.label}</p>
          </div>

          {/* Workout */}
          <div className="p-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center">
            <Dumbbell className="h-4 w-4 text-emerald-400 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Workout</p>
            <div className="flex items-center justify-center gap-1 my-1">
              <Check className="h-5 w-5 text-emerald-400" />
              <span className="text-sm font-medium text-emerald-300">Done</span>
            </div>
            <p className="text-xs text-muted-foreground">{workout.type}</p>
          </div>
        </div>

        {/* Weekly Overview */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Weekly Overview</p>
          <div className="p-3 rounded-xl border border-white/5 bg-white/[0.02]">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground">
                  <td className="pb-2 w-12"></td>
                  {weeklyData.map((d, i) => (
                    <td key={i} className="pb-2 text-center font-medium">
                      {d.day}
                    </td>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Sleep row with bars */}
                <tr>
                  <td className="py-1 text-muted-foreground">Sleep</td>
                  {weeklyData.map((d, i) => (
                    <td key={i} className="py-1">
                      <div className="flex justify-center">
                        <div className="w-4 h-8 bg-white/5 rounded-sm relative overflow-hidden">
                          <div
                            className="absolute bottom-0 w-full bg-blue-400/60 rounded-sm transition-all"
                            style={{ height: `${getSleepBarHeight(d.sleep)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  ))}
                </tr>
                {/* Gym row */}
                <tr>
                  <td className="py-1 text-muted-foreground">Gym</td>
                  {weeklyData.map((d, i) => (
                    <td key={i} className="py-1 text-center">
                      {d.gym === true && <Check className="h-3 w-3 text-emerald-400 mx-auto" />}
                      {d.gym === false && <Minus className="h-3 w-3 text-muted-foreground mx-auto" />}
                      {d.gym === null && <span className="text-muted-foreground/30">--</span>}
                    </td>
                  ))}
                </tr>
                {/* Steps row */}
                <tr>
                  <td className="py-1 text-muted-foreground">Steps</td>
                  {weeklyData.map((d, i) => (
                    <td key={i} className="py-1 text-center stat-number">
                      <span className={d.steps === '--' ? 'text-muted-foreground/30' : ''}>
                        {d.steps}
                      </span>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Trend & Insight */}
        <div className="flex items-center justify-between gap-4 pt-2 border-t border-white/5">
          <div className="flex items-center gap-2 text-xs">
            <TrendingUp className="h-3 w-3 text-emerald-400" />
            <span className="text-muted-foreground">Trend:</span>
            <span className="text-foreground">{trend.metric}</span>
            <span className="text-emerald-400 stat-number">+{trend.change}%</span>
            <span className="text-muted-foreground">{trend.period}</span>
          </div>
        </div>
        <div className="flex items-start gap-2 text-xs p-2.5 rounded-lg border border-orange-500/20 bg-orange-500/5">
          <Lightbulb className="h-3.5 w-3.5 text-orange-400 mt-0.5 flex-shrink-0" />
          <span className="text-orange-200">Insight: {insight.text}</span>
        </div>
      </CardContent>
    </Card>
  );
}
