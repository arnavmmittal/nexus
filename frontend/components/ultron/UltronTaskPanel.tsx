'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Activity,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ChevronRight,
  Zap,
  Shield,
  Settings,
  TrendingUp,
  X,
  Check,
  Eye,
  EyeOff,
} from 'lucide-react';
import type { BackgroundTask, Suggestion, AutonomousAction } from './useUltron';

interface UltronTaskPanelProps {
  backgroundTasks: BackgroundTask[];
  suggestions: Suggestion[];
  recentActions: AutonomousAction[];
  autonomyLevel: number;
  isAutonomousMode: boolean;
  onDismissSuggestion: (id: string) => void;
  onApproveSuggestion: (id: string) => void;
  onRemoveTask: (id: string) => void;
  onSetAutonomyLevel: (level: number) => void;
  onToggleAutonomousMode: () => void;
  className?: string;
}

const statusIcons = {
  pending: Clock,
  running: Activity,
  completed: CheckCircle2,
  failed: XCircle,
};

const statusColors = {
  pending: 'text-amber-400',
  running: 'text-blue-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
};

const priorityColors = {
  low: 'border-gray-500/30 bg-gray-500/10',
  medium: 'border-amber-500/30 bg-amber-500/10',
  high: 'border-orange-500/30 bg-orange-500/10',
  critical: 'border-red-500/30 bg-red-500/10',
};

const categoryIcons = {
  optimization: TrendingUp,
  security: Shield,
  automation: Zap,
  improvement: Settings,
};

export function UltronTaskPanel({
  backgroundTasks,
  suggestions,
  recentActions,
  autonomyLevel,
  isAutonomousMode,
  onDismissSuggestion,
  onApproveSuggestion,
  onRemoveTask,
  onSetAutonomyLevel,
  onToggleAutonomousMode,
  className,
}: UltronTaskPanelProps) {
  const [activeTab, setActiveTab] = useState<'tasks' | 'suggestions' | 'actions'>('tasks');
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const runningTasks = backgroundTasks.filter(t => t.status === 'running');
  const pendingTasks = backgroundTasks.filter(t => t.status === 'pending');
  const completedTasks = backgroundTasks.filter(t => t.status === 'completed' || t.status === 'failed');

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Autonomy Control */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn(
              'w-2 h-2 rounded-full',
              isAutonomousMode ? 'bg-red-500 animate-pulse' : 'bg-gray-500'
            )} />
            <span className="text-sm font-medium">Autonomous Mode</span>
          </div>
          <button
            onClick={onToggleAutonomousMode}
            className={cn(
              'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
              isAutonomousMode
                ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                : 'bg-white/5 text-white/60 border border-white/10 hover:bg-white/10'
            )}
          >
            {isAutonomousMode ? 'Active' : 'Inactive'}
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white/50">Autonomy Level</span>
            <span className="text-red-400 font-mono">{autonomyLevel}%</span>
          </div>
          <div className="relative h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-600 to-red-400 transition-all duration-300"
              style={{ width: `${autonomyLevel}%` }}
            />
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={autonomyLevel}
            onChange={(e) => onSetAutonomyLevel(parseInt(e.target.value))}
            className="w-full h-1 appearance-none bg-transparent cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-red-500"
          />
          <div className="flex justify-between text-[10px] text-white/40">
            <span>Supervised</span>
            <span>Semi-Auto</span>
            <span>Full Auto</span>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-white/10">
        {[
          { id: 'tasks', label: 'Tasks', count: runningTasks.length },
          { id: 'suggestions', label: 'Suggestions', count: suggestions.length },
          { id: 'actions', label: 'Actions', count: recentActions.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              'flex-1 px-3 py-2.5 text-xs font-medium transition-colors relative',
              activeTab === tab.id
                ? 'text-red-400'
                : 'text-white/50 hover:text-white/70'
            )}
          >
            <span className="flex items-center justify-center gap-1.5">
              {tab.label}
              {tab.count > 0 && (
                <span className={cn(
                  'px-1.5 py-0.5 rounded-full text-[10px]',
                  activeTab === tab.id
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-white/10 text-white/50'
                )}>
                  {tab.count}
                </span>
              )}
            </span>
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-red-500" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {/* Tasks Tab */}
        {activeTab === 'tasks' && (
          <>
            {backgroundTasks.length === 0 ? (
              <div className="text-center text-white/40 text-sm py-8">
                No background tasks
              </div>
            ) : (
              <>
                {/* Running Tasks */}
                {runningTasks.map((task) => {
                  const StatusIcon = statusIcons[task.status];
                  const isExpanded = expandedTask === task.id;
                  return (
                    <div
                      key={task.id}
                      className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3"
                    >
                      <div className="flex items-start gap-2">
                        <StatusIcon className={cn('w-4 h-4 mt-0.5 animate-pulse', statusColors[task.status])} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium truncate">{task.name}</span>
                            <button
                              onClick={() => setExpandedTask(isExpanded ? null : task.id)}
                              className="p-1 hover:bg-white/10 rounded"
                            >
                              <ChevronRight className={cn(
                                'w-3 h-3 transition-transform',
                                isExpanded && 'rotate-90'
                              )} />
                            </button>
                          </div>
                          {task.progress !== undefined && (
                            <div className="mt-2">
                              <div className="h-1 rounded-full bg-white/10 overflow-hidden">
                                <div
                                  className="h-full bg-blue-400 transition-all duration-300"
                                  style={{ width: `${task.progress}%` }}
                                />
                              </div>
                              <div className="mt-1 text-[10px] text-white/40">
                                {Math.round(task.progress)}% complete
                              </div>
                            </div>
                          )}
                          {isExpanded && task.description && (
                            <p className="mt-2 text-xs text-white/60">{task.description}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Pending Tasks */}
                {pendingTasks.map((task) => {
                  const StatusIcon = statusIcons[task.status];
                  return (
                    <div
                      key={task.id}
                      className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3"
                    >
                      <div className="flex items-start gap-2">
                        <StatusIcon className={cn('w-4 h-4 mt-0.5', statusColors[task.status])} />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium truncate block">{task.name}</span>
                          {task.description && (
                            <p className="mt-1 text-xs text-white/50">{task.description}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Completed Tasks */}
                {completedTasks.map((task) => {
                  const StatusIcon = statusIcons[task.status];
                  return (
                    <div
                      key={task.id}
                      className="rounded-lg border border-white/10 bg-white/5 p-3 opacity-70"
                    >
                      <div className="flex items-start gap-2">
                        <StatusIcon className={cn('w-4 h-4 mt-0.5', statusColors[task.status])} />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm truncate block">{task.name}</span>
                        </div>
                        <button
                          onClick={() => onRemoveTask(task.id)}
                          className="p-1 hover:bg-white/10 rounded text-white/40 hover:text-white/60"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </>
        )}

        {/* Suggestions Tab */}
        {activeTab === 'suggestions' && (
          <>
            {suggestions.length === 0 ? (
              <div className="text-center text-white/40 text-sm py-8">
                No suggestions pending
              </div>
            ) : (
              suggestions.map((suggestion) => {
                const CategoryIcon = categoryIcons[suggestion.category];
                return (
                  <div
                    key={suggestion.id}
                    className={cn(
                      'rounded-lg border p-3',
                      priorityColors[suggestion.priority]
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <CategoryIcon className="w-4 h-4 mt-0.5 text-white/70" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium">{suggestion.title}</span>
                          <span className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] uppercase font-medium',
                            suggestion.priority === 'critical' && 'bg-red-500/20 text-red-400',
                            suggestion.priority === 'high' && 'bg-orange-500/20 text-orange-400',
                            suggestion.priority === 'medium' && 'bg-amber-500/20 text-amber-400',
                            suggestion.priority === 'low' && 'bg-gray-500/20 text-gray-400'
                          )}>
                            {suggestion.priority}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-white/60">{suggestion.description}</p>
                        <div className="mt-2 flex gap-2">
                          <button
                            onClick={() => onApproveSuggestion(suggestion.id)}
                            className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs hover:bg-emerald-500/30 transition-colors"
                          >
                            <Check className="w-3 h-3" />
                            Approve
                          </button>
                          <button
                            onClick={() => onDismissSuggestion(suggestion.id)}
                            className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 text-white/50 text-xs hover:bg-white/10 transition-colors"
                          >
                            <X className="w-3 h-3" />
                            Dismiss
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </>
        )}

        {/* Actions Tab */}
        {activeTab === 'actions' && (
          <>
            {recentActions.length === 0 ? (
              <div className="text-center text-white/40 text-sm py-8">
                No recent actions
              </div>
            ) : (
              recentActions.map((action) => (
                <div
                  key={action.id}
                  className={cn(
                    'rounded-lg border p-3',
                    action.success
                      ? 'border-emerald-500/20 bg-emerald-500/5'
                      : 'border-red-500/20 bg-red-500/5'
                  )}
                >
                  <div className="flex items-start gap-2">
                    {action.success ? (
                      <CheckCircle2 className="w-4 h-4 mt-0.5 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 mt-0.5 text-red-400" />
                    )}
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium block">{action.action}</span>
                      <p className="mt-0.5 text-xs text-white/50">{action.result}</p>
                      <span className="mt-1 text-[10px] text-white/30 block">
                        {formatTimeAgo(action.timestamp)}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </>
        )}
      </div>
    </div>
  );
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
