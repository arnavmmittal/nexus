'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { useSkillsWidget } from '@/hooks/useWidgets';
import {
  Zap,
  Flame,
  Trophy,
  Loader2,
} from 'lucide-react';

// Map skill categories to icons
const categoryIcons: Record<string, string> = {
  programming: '\uD83D\uDC0D', // snake for python
  coding: '\uD83D\uDC0D',
  python: '\uD83D\uDC0D',
  design: '\uD83C\uDFA8',
  ui: '\uD83C\uDFA8',
  'ui design': '\uD83C\uDFA8',
  data: '\uD83D\uDCCA',
  'data analysis': '\uD83D\uDCCA',
  analytics: '\uD83D\uDCCA',
  javascript: '\uD83D\uDFE8',
  typescript: '\uD83D\uDFE6',
  writing: '\u270D\uFE0F',
  default: '\u2B50',
};

function getSkillIcon(category: string): string {
  const lowerCategory = category.toLowerCase();
  return categoryIcons[lowerCategory] || categoryIcons.default;
}

export function SkillProgress() {
  const { data, isLoading, error } = useSkillsWidget();

  // Fallback mock data
  const mockSkills = [
    { id: '1', name: 'Python', category: 'programming', level: 8, progress: 62, total_xp: 1250 },
    { id: '2', name: 'UI Design', category: 'design', level: 4, progress: 45, total_xp: 800 },
    { id: '3', name: 'Data Analysis', category: 'data', level: 3, progress: 78, total_xp: 500 },
  ];

  const skills = data?.top_skills?.slice(0, 3) || mockSkills;
  const weeklyXP = data?.weekly_xp || 385;
  const dailyGoal = 500;
  const dailyProgress = Math.min((weeklyXP / dailyGoal) * 100, 100);

  // Mock streak data (would come from a different endpoint in real implementation)
  const streaks = [
    { name: 'Coding', days: 23, isHot: true },
    { name: 'Reading', days: 15, isHot: true },
    { name: 'Gym', days: 8, isHot: false },
    { name: 'Meditation', days: 3, isHot: false },
  ];

  const recentAchievement = {
    title: 'Week Warrior',
    description: '7 day coding streak',
  };

  return (
    <Card className="glass-panel-hover border-blue-500/20 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
              <Zap className="h-4 w-4 text-blue-400" />
            </div>
            <CardTitle className="text-sm font-semibold">SKILL PROGRESS</CardTitle>
          </div>
          {isLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Today's XP */}
        <div className="p-4 rounded-xl border border-blue-500/20 bg-blue-500/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Weekly XP</span>
            <span className="stat-number text-2xl font-bold text-blue-300">+{weeklyXP}</span>
          </div>
          <div className="space-y-1">
            <Progress value={dailyProgress} className="h-2 bg-blue-950" />
            <p className="text-xs text-muted-foreground text-right stat-number">
              {weeklyXP}/{dailyGoal} weekly goal
            </p>
          </div>
        </div>

        {/* Skills Practiced */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Top Skills</p>
          <div className="space-y-2">
            {skills.map((skill) => (
              <div
                key={skill.id}
                className="flex items-center gap-3 p-2.5 rounded-lg border border-white/5 bg-white/[0.02]"
              >
                <span className="text-lg">{getSkillIcon(skill.category)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{skill.name}</span>
                    <span className="text-xs text-blue-400 stat-number">+{skill.total_xp} XP</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={skill.progress} className="h-1.5 flex-1" />
                    <span className="text-xs text-muted-foreground stat-number">
                      Lv.{skill.level} → {Math.round(skill.progress)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {error && (
            <p className="text-xs text-muted-foreground">Using fallback data</p>
          )}
        </div>

        {/* Active Streaks */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Flame className="h-3 w-3 text-orange-400" />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Active Streaks</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {streaks.map((streak) => (
              <div
                key={streak.name}
                className={cn(
                  'flex items-center justify-between p-2 rounded-lg border',
                  streak.isHot
                    ? 'border-orange-500/20 bg-orange-500/5'
                    : 'border-white/5 bg-white/[0.02]'
                )}
              >
                <span className="text-sm">{streak.name}</span>
                <div className="flex items-center gap-1">
                  <span className={cn('stat-number text-sm font-medium', streak.isHot && 'text-orange-400')}>
                    {streak.days}
                  </span>
                  {streak.isHot && <Flame className="h-3 w-3 text-orange-400" />}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Achievement */}
        <div className="flex items-center gap-3 p-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5">
          <Trophy className="h-5 w-5 text-yellow-400" />
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-300">{recentAchievement.title}</p>
            <p className="text-xs text-muted-foreground">{recentAchievement.description}</p>
          </div>
          <Badge className="bg-yellow-500/20 text-yellow-300 border-yellow-500/30">New!</Badge>
        </div>
      </CardContent>
    </Card>
  );
}
