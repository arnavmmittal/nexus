'use client';

import { useState } from 'react';
import { useDashboardStore } from '@/stores/dashboard';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Search,
  Bell,
  Flame,
  Trophy,
  Clock,
  X,
} from 'lucide-react';

export function Header() {
  const { sidebarOpen } = useDashboardStore();
  const [showNotifications, setShowNotifications] = useState(false);

  // Get current date
  const today = new Date();
  const dateString = today.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  // Mock data for header stats
  const stats = {
    streak: 23,
    xpToday: 385,
    deepWorkHours: 3.5,
  };

  const notifications = [
    {
      id: 1,
      color: 'bg-emerald-500',
      title: 'Python streak at risk!',
      description: 'Practice today to maintain your 23-day streak',
    },
    {
      id: 2,
      color: 'bg-blue-500',
      title: 'New achievement unlocked!',
      description: 'Week Warrior - 7 consecutive days of coding',
    },
    {
      id: 3,
      color: 'bg-orange-500',
      title: 'Sleep quality insight',
      description: 'Your sleep improved 12% this week',
    },
  ];

  return (
    <header
      className={cn(
        'fixed top-0 right-0 z-30 h-16 border-b border-border bg-background/80 backdrop-blur-xl',
        'transition-all duration-300',
        sidebarOpen ? 'left-56' : 'left-16'
      )}
    >
      <div className="flex h-full items-center justify-between px-6">
        {/* Left: Date and greeting */}
        <div className="flex items-center gap-4">
          <div>
            <p className="text-sm text-muted-foreground">{dateString}</p>
            <h1 className="text-lg font-semibold">Good afternoon, Arnav</h1>
          </div>
        </div>

        {/* Center: Search */}
        <div className="hidden md:flex flex-1 max-w-md mx-8">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search or ask Nexus..."
              className="w-full pl-10 bg-secondary/50 border-border focus:border-emerald-500/50 focus:ring-emerald-500/20"
            />
            <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 hidden sm:inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
              <span className="text-xs">CMD</span>K
            </kbd>
          </div>
        </div>

        {/* Right: Stats and notifications */}
        <div className="flex items-center gap-3">
          {/* Quick Stats */}
          <div className="hidden lg:flex items-center gap-4 mr-4">
            <div className="flex items-center gap-1.5">
              <Flame className="h-4 w-4 text-orange-400" />
              <span className="stat-number text-sm font-medium">{stats.streak}</span>
              <span className="text-xs text-muted-foreground">day streak</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-1.5">
              <Trophy className="h-4 w-4 text-emerald-400" />
              <span className="stat-number text-sm font-medium">+{stats.xpToday}</span>
              <span className="text-xs text-muted-foreground">XP</span>
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-purple-400" />
              <span className="stat-number text-sm font-medium">{stats.deepWorkHours}h</span>
              <span className="text-xs text-muted-foreground">deep work</span>
            </div>
          </div>

          {/* Notifications */}
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              onClick={() => setShowNotifications(!showNotifications)}
            >
              <Bell className="h-5 w-5" />
              <Badge className="absolute -right-1 -top-1 h-5 min-w-5 rounded-full bg-emerald-500 px-1.5 text-[10px] font-medium text-black">
                3
              </Badge>
            </Button>

            {/* Notifications dropdown */}
            {showNotifications && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowNotifications(false)}
                />
                <div className="absolute right-0 top-full mt-2 w-80 z-50 rounded-lg border border-border bg-card shadow-lg">
                  <div className="p-3 border-b border-border flex items-center justify-between">
                    <p className="text-sm font-semibold">Notifications</p>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => setShowNotifications(false)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="p-2 space-y-1">
                    {notifications.map((notification) => (
                      <button
                        key={notification.id}
                        className="w-full flex flex-col items-start gap-1 p-2 rounded-lg hover:bg-white/5 transition-colors text-left"
                        onClick={() => setShowNotifications(false)}
                      >
                        <div className="flex items-center gap-2">
                          <div className={cn('h-2 w-2 rounded-full', notification.color)} />
                          <span className="text-sm font-medium">{notification.title}</span>
                        </div>
                        <span className="text-xs text-muted-foreground ml-4">
                          {notification.description}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* User avatar */}
          <Button variant="ghost" size="icon" className="rounded-full">
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-blue-500 flex items-center justify-center">
              <span className="text-sm font-bold text-white">A</span>
            </div>
          </Button>
        </div>
      </div>
    </header>
  );
}
