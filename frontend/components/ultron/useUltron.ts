'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useVoice, type VoiceState, type UseVoiceReturn } from '@/components/jarvis/useVoice';

export interface BackgroundTask {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  description?: string;
  startedAt: Date;
  completedAt?: Date;
}

export interface Suggestion {
  id: string;
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  category: 'optimization' | 'security' | 'automation' | 'improvement';
  action?: () => void;
  createdAt: Date;
}

export interface AutonomousAction {
  id: string;
  action: string;
  result: string;
  timestamp: Date;
  success: boolean;
}

export interface UseUltronReturn extends UseVoiceReturn {
  // Autonomous mode
  isAutonomousMode: boolean;
  autonomyLevel: number; // 0-100
  startAutonomousMode: () => void;
  stopAutonomousMode: () => void;
  setAutonomyLevel: (level: number) => void;

  // Background tasks
  backgroundTasks: BackgroundTask[];
  getBackgroundTasks: () => BackgroundTask[];
  addBackgroundTask: (task: Omit<BackgroundTask, 'id' | 'startedAt'>) => string;
  updateBackgroundTask: (id: string, updates: Partial<BackgroundTask>) => void;
  removeBackgroundTask: (id: string) => void;

  // Suggestions
  suggestions: Suggestion[];
  getSuggestions: () => Suggestion[];
  addSuggestion: (suggestion: Omit<Suggestion, 'id' | 'createdAt'>) => string;
  dismissSuggestion: (id: string) => void;
  approveSuggestion: (id: string) => void;

  // Autonomous actions log
  recentActions: AutonomousAction[];

  // Delegation
  delegateToJarvis: (task: string) => Promise<void>;
}

export function useUltron(): UseUltronReturn {
  // Use the base voice hook with Ultron-specific settings
  const voice = useVoice({
    useElevenLabs: true,
    persona: 'jarvis', // TODO: Add ultron persona to backend
    continuous: false,
    silenceTimeout: 2000,
    playbackSpeed: 1.0, // Slower, more deliberate than Jarvis
  });

  // Autonomous mode state
  const [isAutonomousMode, setIsAutonomousMode] = useState(false);
  const [autonomyLevel, setAutonomyLevel] = useState(50);
  const autonomousIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Background tasks
  const [backgroundTasks, setBackgroundTasks] = useState<BackgroundTask[]>([
    {
      id: '1',
      name: 'System Optimization',
      status: 'running',
      progress: 67,
      description: 'Analyzing resource allocation patterns',
      startedAt: new Date(Date.now() - 120000),
    },
    {
      id: '2',
      name: 'Security Scan',
      status: 'completed',
      progress: 100,
      description: 'No vulnerabilities detected',
      startedAt: new Date(Date.now() - 300000),
      completedAt: new Date(Date.now() - 60000),
    },
    {
      id: '3',
      name: 'Data Aggregation',
      status: 'pending',
      description: 'Waiting for optimal compute window',
      startedAt: new Date(),
    },
  ]);

  // Suggestions
  const [suggestions, setSuggestions] = useState<Suggestion[]>([
    {
      id: '1',
      title: 'Automate Daily Report',
      description: 'Detected repetitive report generation pattern. Suggest automation.',
      priority: 'medium',
      category: 'automation',
      createdAt: new Date(Date.now() - 3600000),
    },
    {
      id: '2',
      title: 'Optimize Database Queries',
      description: '3 slow queries identified. Can improve by 40%.',
      priority: 'high',
      category: 'optimization',
      createdAt: new Date(Date.now() - 7200000),
    },
  ]);

  // Recent autonomous actions
  const [recentActions, setRecentActions] = useState<AutonomousAction[]>([
    {
      id: '1',
      action: 'Cleared temporary cache files',
      result: 'Freed 2.3GB storage',
      timestamp: new Date(Date.now() - 1800000),
      success: true,
    },
    {
      id: '2',
      action: 'Updated security definitions',
      result: 'Applied 12 new security rules',
      timestamp: new Date(Date.now() - 3600000),
      success: true,
    },
  ]);

  // Autonomous mode controls
  const startAutonomousMode = useCallback(() => {
    setIsAutonomousMode(true);

    // Simulate autonomous background processing
    autonomousIntervalRef.current = setInterval(() => {
      // Update task progress randomly
      setBackgroundTasks(tasks =>
        tasks.map(task => {
          if (task.status === 'running' && task.progress !== undefined) {
            const newProgress = Math.min(100, task.progress + Math.random() * 5);
            if (newProgress >= 100) {
              return { ...task, progress: 100, status: 'completed', completedAt: new Date() };
            }
            return { ...task, progress: newProgress };
          }
          if (task.status === 'pending' && Math.random() > 0.9) {
            return { ...task, status: 'running', progress: 0 };
          }
          return task;
        })
      );
    }, 2000);
  }, []);

  const stopAutonomousMode = useCallback(() => {
    setIsAutonomousMode(false);
    if (autonomousIntervalRef.current) {
      clearInterval(autonomousIntervalRef.current);
      autonomousIntervalRef.current = null;
    }
  }, []);

  // Background task management
  const getBackgroundTasks = useCallback(() => backgroundTasks, [backgroundTasks]);

  const addBackgroundTask = useCallback((task: Omit<BackgroundTask, 'id' | 'startedAt'>): string => {
    const id = Date.now().toString();
    setBackgroundTasks(tasks => [...tasks, { ...task, id, startedAt: new Date() }]);
    return id;
  }, []);

  const updateBackgroundTask = useCallback((id: string, updates: Partial<BackgroundTask>) => {
    setBackgroundTasks(tasks =>
      tasks.map(task => (task.id === id ? { ...task, ...updates } : task))
    );
  }, []);

  const removeBackgroundTask = useCallback((id: string) => {
    setBackgroundTasks(tasks => tasks.filter(task => task.id !== id));
  }, []);

  // Suggestion management
  const getSuggestions = useCallback(() => suggestions, [suggestions]);

  const addSuggestion = useCallback((suggestion: Omit<Suggestion, 'id' | 'createdAt'>): string => {
    const id = Date.now().toString();
    setSuggestions(s => [...s, { ...suggestion, id, createdAt: new Date() }]);
    return id;
  }, []);

  const dismissSuggestion = useCallback((id: string) => {
    setSuggestions(s => s.filter(suggestion => suggestion.id !== id));
  }, []);

  const approveSuggestion = useCallback((id: string) => {
    const suggestion = suggestions.find(s => s.id === id);
    if (suggestion?.action) {
      suggestion.action();
    }
    // Log the action
    setRecentActions(actions => [
      {
        id: Date.now().toString(),
        action: `Approved: ${suggestion?.title}`,
        result: 'Executing suggestion',
        timestamp: new Date(),
        success: true,
      },
      ...actions.slice(0, 9), // Keep last 10 actions
    ]);
    dismissSuggestion(id);
  }, [suggestions, dismissSuggestion]);

  // Delegation to Jarvis
  const delegateToJarvis = useCallback(async (task: string): Promise<void> => {
    // Log the delegation
    setRecentActions(actions => [
      {
        id: Date.now().toString(),
        action: `Delegated to Jarvis: ${task}`,
        result: 'Task handed off',
        timestamp: new Date(),
        success: true,
      },
      ...actions.slice(0, 9),
    ]);

    // In a real implementation, this would communicate with Jarvis
    console.log(`[Ultron] Delegating task to Jarvis: ${task}`);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (autonomousIntervalRef.current) {
        clearInterval(autonomousIntervalRef.current);
      }
    };
  }, []);

  return {
    // Voice capabilities from useVoice
    ...voice,

    // Autonomous mode
    isAutonomousMode,
    autonomyLevel,
    startAutonomousMode,
    stopAutonomousMode,
    setAutonomyLevel,

    // Background tasks
    backgroundTasks,
    getBackgroundTasks,
    addBackgroundTask,
    updateBackgroundTask,
    removeBackgroundTask,

    // Suggestions
    suggestions,
    getSuggestions,
    addSuggestion,
    dismissSuggestion,
    approveSuggestion,

    // Autonomous actions
    recentActions,

    // Delegation
    delegateToJarvis,
  };
}
