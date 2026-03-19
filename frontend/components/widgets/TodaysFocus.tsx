'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Sun,
  Target,
  Clock,
  Play,
  Pause,
  Check,
  RotateCcw,
} from 'lucide-react';

interface Task {
  id: string;
  title: string;
  completed: boolean;
  progress?: number;
}

export function TodaysFocus() {
  // Mock data
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

  const [tasks, setTasks] = useState<Task[]>([
    { id: '1', title: 'Finish Nexus design docs', completed: false, progress: 60 },
    { id: '2', title: 'Generate 5 TikTok videos', completed: false },
    { id: '3', title: 'Review investment portfolio', completed: false },
  ]);

  const [currentFocus] = useState<string>('Nexus Frontend');
  const [timerSeconds, setTimerSeconds] = useState(2722); // 45:22
  const [isTimerRunning, setIsTimerRunning] = useState(true);

  // Timer effect
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isTimerRunning) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isTimerRunning]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const toggleTask = (id: string) => {
    setTasks((prev) =>
      prev.map((task) => (task.id === id ? { ...task, completed: !task.completed } : task))
    );
  };

  const completedCount = tasks.filter((t) => t.completed).length;
  const deepWorkMinutes = Math.floor(timerSeconds / 60);

  return (
    <Card className="glass-panel-hover border-purple-500/20 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
              <Sun className="h-4 w-4 text-purple-400" />
            </div>
            <CardTitle className="text-sm font-semibold">TODAY&apos;S FOCUS</CardTitle>
          </div>
          <Badge variant="secondary" className="text-xs text-muted-foreground">
            {today}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Top 3 Priorities */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
            <Target className="h-3 w-3" />
            Top 3 Priorities
          </div>
          <div className="space-y-2">
            {tasks.map((task, index) => (
              <div
                key={task.id}
                className={cn(
                  'flex items-center gap-3 p-2.5 rounded-lg border border-white/5 bg-white/[0.02] transition-all duration-200',
                  task.completed && 'opacity-50'
                )}
              >
                <button
                  onClick={() => toggleTask(task.id)}
                  className={cn(
                    'flex h-5 w-5 items-center justify-center rounded-full border-2 transition-all duration-200',
                    task.completed
                      ? 'border-emerald-500 bg-emerald-500'
                      : 'border-muted-foreground/40 hover:border-emerald-500'
                  )}
                >
                  {task.completed && <Check className="h-3 w-3 text-black" />}
                </button>
                <span
                  className={cn(
                    'flex-1 text-sm',
                    task.completed && 'line-through text-muted-foreground'
                  )}
                >
                  {index + 1}. {task.title}
                </span>
                {task.progress !== undefined && !task.completed && (
                  <div className="flex items-center gap-2 w-24">
                    <Progress value={task.progress} className="h-1.5" />
                    <span className="stat-number text-xs text-muted-foreground">{task.progress}%</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Current Focus Timer */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
            <Clock className="h-3 w-3" />
            Current Focus
          </div>
          <div className="p-4 rounded-xl border border-purple-500/20 bg-purple-500/5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-muted-foreground">Working on:</span>
              <span className="text-sm font-medium text-purple-300">{currentFocus}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <Progress
                  value={(timerSeconds % 5400) / 54}
                  className="h-2 bg-purple-950"
                />
              </div>
              <span className="stat-number text-2xl font-bold text-purple-300 tabular-nums">
                {formatTime(timerSeconds)}
              </span>
            </div>
            <div className="flex items-center justify-center gap-2 mt-4">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => setIsTimerRunning(!isTimerRunning)}
              >
                {isTimerRunning ? (
                  <>
                    <Pause className="h-4 w-4 mr-1" />
                    Pause
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-1" />
                    Resume
                  </>
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
              >
                <Check className="h-4 w-4 mr-1" />
                Complete
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                Switch
              </Button>
            </div>
          </div>
        </div>

        {/* Today's Stats */}
        <div className="flex items-center justify-between text-sm text-muted-foreground pt-2 border-t border-white/5">
          <span>
            Today: <span className="text-foreground font-medium stat-number">{Math.floor(deepWorkMinutes / 60)}h {deepWorkMinutes % 60}m</span> deep work
          </span>
          <span>
            <span className="text-foreground font-medium">{completedCount}</span> tasks completed
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
