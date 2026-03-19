'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Target,
  Wallet,
  BookOpen,
  Dumbbell,
  Clock,
} from 'lucide-react';

interface Goal {
  title: string;
  target: string;
  current: string;
  percentage: number;
  color: string;
}

interface GoalCategory {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  goals: Goal[];
}

export function GoalProgress() {
  const quarter = 'Q1 2026';

  const categories: GoalCategory[] = [
    {
      name: 'Financial',
      icon: Wallet,
      color: 'emerald',
      goals: [
        { title: 'Net Worth', target: '$100K', current: '$47,832', percentage: 47.8, color: 'emerald' },
        { title: 'Monthly Income', target: '$10K/mo', current: '$4,250', percentage: 42.5, color: 'emerald' },
      ],
    },
    {
      name: 'Learning',
      icon: BookOpen,
      color: 'blue',
      goals: [
        { title: 'Python Mastery', target: 'Level 15', current: 'Lv.8', percentage: 53, color: 'blue' },
        { title: 'Ship Projects', target: '5 projects', current: '3/5', percentage: 60, color: 'blue' },
      ],
    },
    {
      name: 'Fitness',
      icon: Dumbbell,
      color: 'orange',
      goals: [
        { title: 'Bench Press', target: '225 lbs', current: '185 lbs', percentage: 82, color: 'orange' },
        { title: '5K Time', target: '< 25 min', current: '28 min', percentage: 89, color: 'orange' },
      ],
    },
    {
      name: 'Time',
      icon: Clock,
      color: 'purple',
      goals: [
        { title: 'Deep Work', target: '100 hrs/mo', current: '68 hrs', percentage: 68, color: 'purple' },
      ],
    },
  ];

  const getProgressColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: 'bg-emerald-500',
      blue: 'bg-blue-500',
      orange: 'bg-orange-500',
      purple: 'bg-purple-500',
    };
    return colors[color] || 'bg-white';
  };

  const getBorderColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: 'border-emerald-500/20',
      blue: 'border-blue-500/20',
      orange: 'border-orange-500/20',
      purple: 'border-purple-500/20',
    };
    return colors[color] || 'border-white/10';
  };

  const getBgColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: 'bg-emerald-500/5',
      blue: 'bg-blue-500/5',
      orange: 'bg-orange-500/5',
      purple: 'bg-purple-500/5',
    };
    return colors[color] || 'bg-white/5';
  };

  const getIconColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: 'text-emerald-400',
      blue: 'text-blue-400',
      orange: 'text-orange-400',
      purple: 'text-purple-400',
    };
    return colors[color] || 'text-white';
  };

  return (
    <Card className="glass-panel-hover border-white/10 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
              <Target className="h-4 w-4 text-white" />
            </div>
            <CardTitle className="text-sm font-semibold">GOAL PROGRESS</CardTitle>
          </div>
          <Badge variant="secondary" className="text-xs text-muted-foreground">
            {quarter}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {categories.map((category) => {
          const Icon = category.icon;
          return (
            <div key={category.name} className="space-y-2">
              <div className="flex items-center gap-2">
                <Icon className={cn('h-4 w-4', getIconColor(category.color))} />
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {category.name}
                </p>
              </div>
              <div className={cn('p-3 rounded-xl border', getBorderColor(category.color), getBgColor(category.color))}>
                {category.goals.map((goal, idx) => (
                  <div key={goal.title} className={cn(idx > 0 && 'mt-3 pt-3 border-t border-white/5')}>
                    <div className="flex items-center justify-between text-sm mb-1.5">
                      <span className="text-muted-foreground">{goal.title}: <span className="text-foreground font-medium">{goal.target}</span></span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 relative">
                        <div className="h-3 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className={cn('h-full rounded-full transition-all duration-500', getProgressColor(goal.color))}
                            style={{ width: `${goal.percentage}%` }}
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="stat-number font-medium">{goal.current}</span>
                        <span className="stat-number text-muted-foreground">({goal.percentage}%)</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
