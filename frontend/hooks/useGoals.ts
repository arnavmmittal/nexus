'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { type Goal, type GoalCreate, type GoalProgressCreate } from '@/lib/api';

// Query keys
export const goalKeys = {
  all: ['goals'] as const,
  lists: () => [...goalKeys.all, 'list'] as const,
  list: (filters: { status?: string; domain?: string }) => [...goalKeys.lists(), filters] as const,
  details: () => [...goalKeys.all, 'detail'] as const,
  detail: (id: string) => [...goalKeys.details(), id] as const,
  widget: () => [...goalKeys.all, 'widget'] as const,
};

// Get all goals
export function useGoals(options?: { status?: string; domain?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: goalKeys.list({ status: options?.status, domain: options?.domain }),
    queryFn: () => api.getGoals(options),
  });
}

// Get single goal with history
export function useGoal(goalId: string) {
  return useQuery({
    queryKey: goalKeys.detail(goalId),
    queryFn: () => api.getGoal(goalId),
    enabled: !!goalId,
  });
}

// Get goals widget data
export function useGoalsWidget() {
  return useQuery({
    queryKey: goalKeys.widget(),
    queryFn: () => api.getGoalsWidget(),
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Create goal mutation
export function useCreateGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: GoalCreate) => api.createGoal(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
      queryClient.invalidateQueries({ queryKey: goalKeys.widget() });
    },
  });
}

// Update goal mutation
export function useUpdateGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ goalId, data }: { goalId: string; data: Partial<GoalCreate & { status?: string }> }) =>
      api.updateGoal(goalId, data),
    onSuccess: (updatedGoal) => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
      queryClient.invalidateQueries({ queryKey: goalKeys.widget() });
      queryClient.setQueryData(goalKeys.detail(updatedGoal.id), (old: { goal: Goal; progress_history: unknown[] } | undefined) =>
        old ? { ...old, goal: updatedGoal } : undefined
      );
    },
  });
}

// Log progress mutation
export function useLogGoalProgress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ goalId, data }: { goalId: string; data: GoalProgressCreate }) =>
      api.logGoalProgress(goalId, data),
    onSuccess: (updatedGoal) => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
      queryClient.invalidateQueries({ queryKey: goalKeys.widget() });
      queryClient.setQueryData(goalKeys.detail(updatedGoal.id), (old: { goal: Goal; progress_history: unknown[] } | undefined) =>
        old ? { ...old, goal: updatedGoal } : undefined
      );
    },
  });
}

// Delete goal mutation
export function useDeleteGoal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (goalId: string) => api.deleteGoal(goalId),
    onSuccess: (_, goalId) => {
      queryClient.invalidateQueries({ queryKey: goalKeys.lists() });
      queryClient.invalidateQueries({ queryKey: goalKeys.widget() });
      queryClient.removeQueries({ queryKey: goalKeys.detail(goalId) });
    },
  });
}
