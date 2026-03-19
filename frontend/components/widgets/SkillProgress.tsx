'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Zap,
  Flame,
  Trophy,
  Code2,
  Palette,
  BarChart3,
  Book,
  Dumbbell,
} from 'lucide-react';

interface Skill {
  name: string;
  icon: string;
  xpToday: number;
  level: number;
  progressToNext: number;
}

interface Streak {
  name: string;
  days: number;
  isHot: boolean;
}

export function SkillProgress() {
  // Mock data
  const dailyXP = 385;
  const dailyGoal = 500;
  const dailyProgress = (dailyXP / dailyGoal) * 100;

  const skills: Skill[] = [
    { name: 'Python', icon: '🐍', xpToday: 125, level: 8, progressToNext: 62 },
    { name: 'UI Design', icon: '🎨', xpToday: 80, level: 4, progressToNext: 45 },
    { name: 'Data Analysis', icon: '📊', xpToday: 50, level: 3, progressToNext: 78 },
  ];

  const streaks: Streak[] = [
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
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
            <Zap className="h-4 w-4 text-blue-400" />
          </div>
          <CardTitle className="text-sm font-semibold">SKILL PROGRESS</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Today's XP */}
        <div className="p-4 rounded-xl border border-blue-500/20 bg-blue-500/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Today&apos;s XP</span>
            <span className="stat-number text-2xl font-bold text-blue-300">+{dailyXP}</span>
          </div>
          <div className="space-y-1">
            <Progress value={dailyProgress} className="h-2 bg-blue-950" />
            <p className="text-xs text-muted-foreground text-right stat-number">
              {dailyXP}/{dailyGoal} daily goal
            </p>
          </div>
        </div>

        {/* Skills Practiced */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Skills Practiced</p>
          <div className="space-y-2">
            {skills.map((skill) => (
              <div
                key={skill.name}
                className="flex items-center gap-3 p-2.5 rounded-lg border border-white/5 bg-white/[0.02]"
              >
                <span className="text-lg">{skill.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{skill.name}</span>
                    <span className="text-xs text-blue-400 stat-number">+{skill.xpToday} XP</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={skill.progressToNext} className="h-1.5 flex-1" />
                    <span className="text-xs text-muted-foreground stat-number">
                      Lv.{skill.level} → {skill.progressToNext}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
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
