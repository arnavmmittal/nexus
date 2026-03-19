'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useGoalsWidget } from '@/hooks/useWidgets';
import {
  Target,
  Wallet,
  BookOpen,
  Dumbbell,
  Clock,
  Loader2,
  Briefcase,
  Heart,
  Lightbulb,
} from 'lucide-react';

// Map domains to icons and colors
const domainConfig: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string }> = {
  financial: { icon: Wallet, color: 'emerald' },
  finance: { icon: Wallet, color: 'emerald' },
  money: { icon: Wallet, color: 'emerald' },
  learning: { icon: BookOpen, color: 'blue' },
  education: { icon: BookOpen, color: 'blue' },
  skills: { icon: BookOpen, color: 'blue' },
  fitness: { icon: Dumbbell, color: 'orange' },
  health: { icon: Heart, color: 'orange' },
  exercise: { icon: Dumbbell, color: 'orange' },
  time: { icon: Clock, color: 'purple' },
  productivity: { icon: Clock, color: 'purple' },
  career: { icon: Briefcase, color: 'cyan' },
  work: { icon: Briefcase, color: 'cyan' },
  personal: { icon: Lightbulb, color: 'yellow' },
};

function getDomainConfig(domain: string) {
  const lowerDomain = domain.toLowerCase();
  return domainConfig[lowerDomain] || { icon: Target, color: 'white' };
}

const getProgressColor = (color: string) => {
  const colors: Record<string, string> = {
    emerald: 'bg-emerald-500',
    blue: 'bg-blue-500',
    orange: 'bg-orange-500',
    purple: 'bg-purple-500',
    cyan: 'bg-cyan-500',
    yellow: 'bg-yellow-500',
    white: 'bg-white',
  };
  return colors[color] || 'bg-white';
};

const getBorderColor = (color: string) => {
  const colors: Record<string, string> = {
    emerald: 'border-emerald-500/20',
    blue: 'border-blue-500/20',
    orange: 'border-orange-500/20',
    purple: 'border-purple-500/20',
    cyan: 'border-cyan-500/20',
    yellow: 'border-yellow-500/20',
    white: 'border-white/10',
  };
  return colors[color] || 'border-white/10';
};

const getBgColor = (color: string) => {
  const colors: Record<string, string> = {
    emerald: 'bg-emerald-500/5',
    blue: 'bg-blue-500/5',
    orange: 'bg-orange-500/5',
    purple: 'bg-purple-500/5',
    cyan: 'bg-cyan-500/5',
    yellow: 'bg-yellow-500/5',
    white: 'bg-white/5',
  };
  return colors[color] || 'bg-white/5';
};

const getIconColor = (color: string) => {
  const colors: Record<string, string> = {
    emerald: 'text-emerald-400',
    blue: 'text-blue-400',
    orange: 'text-orange-400',
    purple: 'text-purple-400',
    cyan: 'text-cyan-400',
    yellow: 'text-yellow-400',
    white: 'text-white',
  };
  return colors[color] || 'text-white';
};

export function GoalProgress() {
  const { data, isLoading, error } = useGoalsWidget();

  const quarter = 'Q1 2026';

  // Transform API data into display format
  const categories = data?.by_domain
    ? Object.entries(data.by_domain).map(([domain, goals]) => {
        const config = getDomainConfig(domain);
        return {
          name: domain.charAt(0).toUpperCase() + domain.slice(1),
          icon: config.icon,
          color: config.color,
          goals: goals.map((goal) => ({
            title: goal.title,
            target: goal.deadline ? `Due ${new Date(goal.deadline).toLocaleDateString()}` : 'No deadline',
            current: `${Math.round(goal.progress)}%`,
            percentage: goal.progress,
            color: config.color,
          })),
        };
      })
    : [
        // Fallback mock data
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
          <div className="flex items-center gap-2">
            {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
            <Badge variant="secondary" className="text-xs text-muted-foreground">
              {quarter}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary stats */}
        {data && (
          <div className="flex items-center gap-4 text-sm mb-2">
            <span className="text-muted-foreground">
              Active: <span className="text-foreground font-medium">{data.active_count}</span>
            </span>
            <span className="text-muted-foreground">
              Completed: <span className="text-emerald-400 font-medium">{data.completed_count}</span>
            </span>
          </div>
        )}

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
                        <span className="stat-number text-muted-foreground">({Math.round(goal.percentage)}%)</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {error && (
          <p className="text-xs text-muted-foreground text-center pt-2">Using fallback data</p>
        )}
      </CardContent>
    </Card>
  );
}
