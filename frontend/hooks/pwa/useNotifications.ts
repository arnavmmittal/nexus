'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import api from '@/lib/api';

export interface NotificationPermission {
  status: 'default' | 'granted' | 'denied' | 'unsupported';
}

export interface UseNotificationsReturn extends NotificationPermission {
  isSubscribed: boolean;
  isLoading: boolean;
  requestPermission: () => Promise<boolean>;
  subscribe: () => Promise<boolean>;
  unsubscribe: () => Promise<boolean>;
  sendTestNotification: () => Promise<boolean>;
}

export function useNotifications(): UseNotificationsReturn {
  const [status, setStatus] = useState<NotificationPermission['status']>('default');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const subscriptionRef = useRef<PushSubscription | null>(null);

  // Check notification permission and subscription status
  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (!('Notification' in window)) {
      setStatus('unsupported');
      return;
    }

    setStatus(Notification.permission as NotificationPermission['status']);

    // Check if already subscribed
    checkSubscription();
  }, []);

  const checkSubscription = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      return;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        subscriptionRef.current = subscription;
        setIsSubscribed(true);
      }
    } catch (error) {
      console.error('[Notifications] Error checking subscription:', error);
    }
  };

  // Request notification permission
  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (!('Notification' in window)) {
      console.log('[Notifications] Not supported');
      return false;
    }

    if (Notification.permission === 'granted') {
      setStatus('granted');
      return true;
    }

    if (Notification.permission === 'denied') {
      setStatus('denied');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      setStatus(permission as NotificationPermission['status']);
      return permission === 'granted';
    } catch (error) {
      console.error('[Notifications] Permission request failed:', error);
      return false;
    }
  }, []);

  // Subscribe to push notifications
  const subscribe = useCallback(async (): Promise<boolean> => {
    if (status !== 'granted') {
      const granted = await requestPermission();
      if (!granted) return false;
    }

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.log('[Notifications] Push not supported');
      return false;
    }

    setIsLoading(true);

    try {
      const registration = await navigator.serviceWorker.ready;

      // Get VAPID public key from server
      const vapidResponse = await api.getVAPIDPublicKey();
      if (!vapidResponse.publicKey) {
        throw new Error('VAPID key not configured on server');
      }

      // Convert VAPID key to Uint8Array
      const vapidKey = urlBase64ToUint8Array(vapidResponse.publicKey);

      // Subscribe to push
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapidKey as BufferSource,
      });

      subscriptionRef.current = subscription;

      // Send subscription to server
      await api.subscribePush(subscription.toJSON());

      setIsSubscribed(true);
      console.log('[Notifications] Subscribed successfully');
      return true;

    } catch (error) {
      console.error('[Notifications] Subscribe failed:', error);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [status, requestPermission]);

  // Unsubscribe from push notifications
  const unsubscribe = useCallback(async (): Promise<boolean> => {
    setIsLoading(true);

    try {
      if (subscriptionRef.current) {
        // Unsubscribe from browser
        await subscriptionRef.current.unsubscribe();

        // Remove from server
        await api.unsubscribePush(subscriptionRef.current.endpoint);

        subscriptionRef.current = null;
        setIsSubscribed(false);
        console.log('[Notifications] Unsubscribed successfully');
        return true;
      }
      return false;
    } catch (error) {
      console.error('[Notifications] Unsubscribe failed:', error);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Send a test notification
  const sendTestNotification = useCallback(async (): Promise<boolean> => {
    if (!isSubscribed) {
      console.log('[Notifications] Not subscribed');
      return false;
    }

    try {
      await api.sendTestPush();
      console.log('[Notifications] Test notification sent');
      return true;
    } catch (error) {
      console.error('[Notifications] Test notification failed:', error);
      return false;
    }
  }, [isSubscribed]);

  return {
    status,
    isSubscribed,
    isLoading,
    requestPermission,
    subscribe,
    unsubscribe,
    sendTestNotification,
  };
}

// Helper to convert VAPID key
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}
