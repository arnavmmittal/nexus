'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

// Query keys
export const widgetKeys = {
  all: ['widgets'] as const,
  today: () => [...widgetKeys.all, 'today'] as const,
  money: () => [...widgetKeys.all, 'money'] as const,
  skills: () => [...widgetKeys.all, 'skills'] as const,
  health: () => [...widgetKeys.all, 'health'] as const,
  goals: () => [...widgetKeys.all, 'goals'] as const,
};

// Today's focus widget data
export function useTodaysFocus() {
  return useQuery({
    queryKey: widgetKeys.today(),
    queryFn: () => api.getTodaysFocus(),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });
}

// Money dashboard widget data
export function useMoneyWidget() {
  return useQuery({
    queryKey: widgetKeys.money(),
    queryFn: () => api.getMoneyData(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Skills widget data
export function useSkillsWidget() {
  return useQuery({
    queryKey: widgetKeys.skills(),
    queryFn: () => api.getSkillsWidget(),
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Health snapshot widget data
export function useHealthWidget() {
  return useQuery({
    queryKey: widgetKeys.health(),
    queryFn: () => api.getHealthData(),
    staleTime: 60 * 1000, // 1 minute
  });
}

// Goals widget data
export function useGoalsWidget() {
  return useQuery({
    queryKey: widgetKeys.goals(),
    queryFn: () => api.getGoalsWidget(),
    staleTime: 30 * 1000, // 30 seconds
  });
}
