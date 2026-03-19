'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import api, { type ChatRequest, type ChatResponse } from '@/lib/api';

interface StreamEvent {
  type: 'content' | 'done' | 'error';
  content?: string;
  conversation_id?: string;
  error?: string;
}

interface UseChatOptions {
  onStreamChunk?: (chunk: string) => void;
  onStreamComplete?: (fullResponse: string) => void;
  onError?: (error: Error) => void;
}

// Non-streaming chat
export function useChat() {
  return useMutation({
    mutationFn: (request: ChatRequest) => api.sendMessage(request),
  });
}

// Streaming chat via WebSocket
export function useStreamingChat(options?: UseChatOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const responseAccumulatorRef = useRef('');

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = api.getWebSocketUrl();
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      options?.onError?.(new Error('WebSocket connection failed'));
    };

    ws.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);

        if (data.type === 'content' && data.content) {
          responseAccumulatorRef.current += data.content;
          setCurrentResponse(responseAccumulatorRef.current);
          options?.onStreamChunk?.(data.content);

          if (data.conversation_id) {
            setConversationId(data.conversation_id);
          }
        } else if (data.type === 'done') {
          setIsStreaming(false);
          options?.onStreamComplete?.(responseAccumulatorRef.current);
        } else if (data.type === 'error') {
          setIsStreaming(false);
          options?.onError?.(new Error(data.error || 'Stream error'));
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    wsRef.current = ws;
  }, [options]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Send a message
  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      // Wait for connection before sending
      setTimeout(() => sendMessage(content), 500);
      return;
    }

    setIsStreaming(true);
    setCurrentResponse('');
    responseAccumulatorRef.current = '';

    wsRef.current.send(JSON.stringify({
      type: 'chat_message',
      content,
    }));
  }, [connect]);

  // Ping to keep connection alive
  const ping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
    ping,
    isConnected,
    isStreaming,
    currentResponse,
    conversationId,
  };
}

// Simple non-streaming chat hook for component use
export function useChatMutation() {
  const mutation = useChat();

  const sendMessage = useCallback(async (message: string, conversationId?: string): Promise<ChatResponse> => {
    return mutation.mutateAsync({ message, conversation_id: conversationId });
  }, [mutation]);

  return {
    sendMessage,
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}
