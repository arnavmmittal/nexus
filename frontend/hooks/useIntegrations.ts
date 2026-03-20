'use client';

import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usePlaidLink, PlaidLinkOptions, PlaidLinkOnSuccess } from 'react-plaid-link';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============ Types ============
export interface Integration {
  id: string;
  type: 'google_calendar' | 'github' | 'plaid';
  status: 'connected' | 'not_connected' | 'error';
  connected_at?: string;
  metadata?: Record<string, unknown>;
}

export interface GoogleCalendarConnection {
  status: 'connected' | 'not_connected';
  email?: string;
  connected_at?: string;
}

export interface GitHubConnection {
  status: 'connected' | 'not_connected';
  username?: string;
  connected_at?: string;
  last_synced?: string;
}

export interface PlaidAccount {
  id: string;
  name: string;
  official_name?: string;
  type: string;
  subtype?: string;
  mask?: string;
  current_balance?: number;
  available_balance?: number;
  institution_name?: string;
  connected_at: string;
}

export interface PlaidConnection {
  status: 'connected' | 'not_connected';
  accounts: PlaidAccount[];
}

export interface IntegrationsStatus {
  google_calendar: GoogleCalendarConnection;
  github: GitHubConnection;
  plaid: PlaidConnection;
}

// ============ Query Keys ============
export const integrationKeys = {
  all: ['integrations'] as const,
  status: () => [...integrationKeys.all, 'status'] as const,
  google: () => [...integrationKeys.all, 'google'] as const,
  github: () => [...integrationKeys.all, 'github'] as const,
  plaid: () => [...integrationKeys.all, 'plaid'] as const,
  plaidLinkToken: () => [...integrationKeys.all, 'plaid', 'link-token'] as const,
};

// ============ API Functions ============
async function fetchIntegrationsStatus(): Promise<IntegrationsStatus> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/status`);
  if (!response.ok) {
    // Return default disconnected status if endpoint doesn't exist yet
    return {
      google_calendar: { status: 'not_connected' },
      github: { status: 'not_connected' },
      plaid: { status: 'not_connected', accounts: [] },
    };
  }
  return response.json();
}

async function connectGoogleCalendar(): Promise<{ auth_url: string }> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/google/connect`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to initiate Google connection');
  return response.json();
}

async function disconnectGoogleCalendar(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/google/disconnect`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to disconnect Google');
}

async function connectGitHub(token: string): Promise<GitHubConnection> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/github/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: token }),
  });
  if (!response.ok) throw new Error('Failed to connect GitHub');
  return response.json();
}

async function disconnectGitHub(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/github/disconnect`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to disconnect GitHub');
}

async function syncGitHub(): Promise<{ synced_at: string }> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/github/sync`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to sync GitHub');
  return response.json();
}

async function createPlaidLinkToken(): Promise<{ link_token: string }> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/plaid/link-token`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to create Plaid link token');
  return response.json();
}

async function exchangePlaidToken(publicToken: string, metadata: unknown): Promise<PlaidConnection> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/plaid/exchange`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ public_token: publicToken, metadata }),
  });
  if (!response.ok) throw new Error('Failed to exchange Plaid token');
  return response.json();
}

async function disconnectPlaidAccount(accountId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/integrations/plaid/accounts/${accountId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to disconnect Plaid account');
}

// ============ Hooks ============

/**
 * Hook to get all integrations status
 */
export function useIntegrationsStatus() {
  return useQuery({
    queryKey: integrationKeys.status(),
    queryFn: fetchIntegrationsStatus,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook for Google Calendar integration
 */
export function useGoogleAuth() {
  const queryClient = useQueryClient();

  const connectMutation = useMutation({
    mutationFn: connectGoogleCalendar,
    onSuccess: (data) => {
      // Open OAuth flow in a popup or redirect
      window.open(data.auth_url, '_blank', 'width=600,height=700');
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectGoogleCalendar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  return {
    connect: connectMutation.mutate,
    disconnect: disconnectMutation.mutate,
    isConnecting: connectMutation.isPending,
    isDisconnecting: disconnectMutation.isPending,
    error: connectMutation.error || disconnectMutation.error,
  };
}

/**
 * Hook for GitHub integration
 */
export function useGitHub() {
  const queryClient = useQueryClient();

  const connectMutation = useMutation({
    mutationFn: connectGitHub,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectGitHub,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncGitHub,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  return {
    connect: connectMutation.mutate,
    disconnect: disconnectMutation.mutate,
    sync: syncMutation.mutate,
    isConnecting: connectMutation.isPending,
    isDisconnecting: disconnectMutation.isPending,
    isSyncing: syncMutation.isPending,
    error: connectMutation.error || disconnectMutation.error || syncMutation.error,
  };
}

/**
 * Hook for Plaid integration
 */
export function usePlaidIntegration() {
  const queryClient = useQueryClient();
  const [linkToken, setLinkToken] = useState<string | null>(null);

  // Fetch link token on mount
  const linkTokenQuery = useQuery({
    queryKey: integrationKeys.plaidLinkToken(),
    queryFn: createPlaidLinkToken,
    staleTime: 30 * 60 * 1000, // 30 minutes
    enabled: false, // Don't auto-fetch, manually trigger
  });

  const exchangeMutation = useMutation({
    mutationFn: ({ publicToken, metadata }: { publicToken: string; metadata: unknown }) =>
      exchangePlaidToken(publicToken, metadata),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectPlaidAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.status() });
    },
  });

  const onSuccess: PlaidLinkOnSuccess = useCallback((publicToken, metadata) => {
    exchangeMutation.mutate({ publicToken, metadata });
  }, [exchangeMutation]);

  const config: PlaidLinkOptions = {
    token: linkToken,
    onSuccess,
    onExit: () => {
      // User exited without completing
    },
  };

  const { open, ready } = usePlaidLink(config);

  const initiatePlaidLink = useCallback(async () => {
    try {
      const data = await linkTokenQuery.refetch();
      if (data.data?.link_token) {
        setLinkToken(data.data.link_token);
      }
    } catch {
      console.error('Failed to create link token');
    }
  }, [linkTokenQuery]);

  // Open Plaid Link when token is ready
  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  return {
    openPlaidLink: initiatePlaidLink,
    disconnectAccount: disconnectMutation.mutate,
    isLoading: linkTokenQuery.isFetching || exchangeMutation.isPending,
    isDisconnecting: disconnectMutation.isPending,
    error: linkTokenQuery.error || exchangeMutation.error || disconnectMutation.error,
    ready,
  };
}
