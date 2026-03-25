'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export interface PWAStatus {
  isInstalled: boolean;
  isInstallable: boolean;
  isOnline: boolean;
  isStandalone: boolean;
  isUpdateAvailable: boolean;
  serviceWorkerStatus: 'unsupported' | 'installing' | 'waiting' | 'active' | 'error';
}

export interface UsePWAReturn extends PWAStatus {
  install: () => Promise<boolean>;
  update: () => void;
  dismissInstall: () => void;
}

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function usePWA(): UsePWAReturn {
  const [isInstalled, setIsInstalled] = useState(false);
  const [isInstallable, setIsInstallable] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isUpdateAvailable, setIsUpdateAvailable] = useState(false);
  const [serviceWorkerStatus, setServiceWorkerStatus] = useState<PWAStatus['serviceWorkerStatus']>('unsupported');

  const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null);
  const registrationRef = useRef<ServiceWorkerRegistration | null>(null);

  // Check if running in standalone mode
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const checkStandalone = () => {
      const isStandaloneMode =
        window.matchMedia('(display-mode: standalone)').matches ||
        (window.navigator as Navigator & { standalone?: boolean }).standalone === true ||
        document.referrer.includes('android-app://');

      setIsStandalone(isStandaloneMode);
      setIsInstalled(isStandaloneMode);
    };

    checkStandalone();

    // Listen for display mode changes
    const mediaQuery = window.matchMedia('(display-mode: standalone)');
    const handleChange = () => checkStandalone();

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      // Fallback for older browsers
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, []);

  // Check online status
  useEffect(() => {
    if (typeof window === 'undefined') return;

    setIsOnline(navigator.onLine);

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Handle install prompt
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      deferredPromptRef.current = e as BeforeInstallPromptEvent;
      setIsInstallable(true);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setIsInstallable(false);
      deferredPromptRef.current = null;
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  // Register service worker
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      setServiceWorkerStatus('unsupported');
      return;
    }

    const registerServiceWorker = async () => {
      try {
        setServiceWorkerStatus('installing');

        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
        });

        registrationRef.current = registration;

        // Check current state
        if (registration.installing) {
          setServiceWorkerStatus('installing');
        } else if (registration.waiting) {
          setServiceWorkerStatus('waiting');
          setIsUpdateAvailable(true);
        } else if (registration.active) {
          setServiceWorkerStatus('active');
        }

        // Listen for updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setIsUpdateAvailable(true);
                setServiceWorkerStatus('waiting');
              }
            });
          }
        });

        // Listen for controller change (after update)
        navigator.serviceWorker.addEventListener('controllerchange', () => {
          setIsUpdateAvailable(false);
          setServiceWorkerStatus('active');
        });

        // Listen for messages from service worker
        navigator.serviceWorker.addEventListener('message', (event) => {
          if (event.data.type === 'sync-complete') {
            console.log('[PWA] Sync complete:', event.data.count, 'actions');
          }
          if (event.data.type === 'notification-click') {
            console.log('[PWA] Notification clicked:', event.data.data);
          }
        });

        // Check for updates periodically
        setInterval(() => {
          registration.update();
        }, 60 * 60 * 1000); // Every hour

      } catch (error) {
        console.error('[PWA] Service worker registration failed:', error);
        setServiceWorkerStatus('error');
      }
    };

    registerServiceWorker();
  }, []);

  // Install the PWA
  const install = useCallback(async (): Promise<boolean> => {
    if (!deferredPromptRef.current) {
      console.log('[PWA] No install prompt available');
      return false;
    }

    try {
      await deferredPromptRef.current.prompt();
      const { outcome } = await deferredPromptRef.current.userChoice;

      if (outcome === 'accepted') {
        console.log('[PWA] User accepted install prompt');
        setIsInstalled(true);
        setIsInstallable(false);
        deferredPromptRef.current = null;
        return true;
      } else {
        console.log('[PWA] User dismissed install prompt');
        return false;
      }
    } catch (error) {
      console.error('[PWA] Install failed:', error);
      return false;
    }
  }, []);

  // Update the service worker
  const update = useCallback(() => {
    if (registrationRef.current?.waiting) {
      // Tell waiting SW to take over
      registrationRef.current.waiting.postMessage({ type: 'skip-waiting' });
      // Reload to use new SW
      window.location.reload();
    }
  }, []);

  // Dismiss install prompt
  const dismissInstall = useCallback(() => {
    setIsInstallable(false);
    deferredPromptRef.current = null;

    // Store dismissal in localStorage
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  }, []);

  return {
    isInstalled,
    isInstallable,
    isOnline,
    isStandalone,
    isUpdateAvailable,
    serviceWorkerStatus,
    install,
    update,
    dismissInstall,
  };
}
