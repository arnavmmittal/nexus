'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { type Skill, type SkillCreate, type SkillXPLogCreate } from '@/lib/api';

// Query keys
export const skillKeys = {
  all: ['skills'] as const,
  lists: () => [...skillKeys.all, 'list'] as const,
  list: (filters: { category?: string }) => [...skillKeys.lists(), filters] as const,
  details: () => [...skillKeys.all, 'detail'] as const,
  detail: (id: string) => [...skillKeys.details(), id] as const,
  widget: () => [...skillKeys.all, 'widget'] as const,
};

// Get all skills
export function useSkills(options?: { category?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: skillKeys.list({ category: options?.category }),
    queryFn: () => api.getSkills(options),
  });
}

// Get single skill with history
export function useSkill(skillId: string) {
  return useQuery({
    queryKey: skillKeys.detail(skillId),
    queryFn: () => api.getSkill(skillId),
    enabled: !!skillId,
  });
}

// Get skills widget data
export function useSkillsWidget() {
  return useQuery({
    queryKey: skillKeys.widget(),
    queryFn: () => api.getSkillsWidget(),
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Create skill mutation
export function useCreateSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SkillCreate) => api.createSkill(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
      queryClient.invalidateQueries({ queryKey: skillKeys.widget() });
    },
  });
}

// Log XP mutation
export function useLogSkillXP() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ skillId, data }: { skillId: string; data: SkillXPLogCreate }) =>
      api.logSkillXP(skillId, data),
    onSuccess: (updatedSkill) => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
      queryClient.invalidateQueries({ queryKey: skillKeys.widget() });
      queryClient.setQueryData(skillKeys.detail(updatedSkill.id), (old: { skill: Skill; history: unknown[] } | undefined) =>
        old ? { ...old, skill: updatedSkill } : undefined
      );
    },
  });
}

// Delete skill mutation
export function useDeleteSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (skillId: string) => api.deleteSkill(skillId),
    onSuccess: (_, skillId) => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
      queryClient.invalidateQueries({ queryKey: skillKeys.widget() });
      queryClient.removeQueries({ queryKey: skillKeys.detail(skillId) });
    },
  });
}
