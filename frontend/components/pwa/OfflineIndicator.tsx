'use client';

import { WifiOff, RefreshCw } from 'lucide-react';
import { usePWA } from '@/hooks/pwa';

export function OfflineIndicator() {
  const { isOnline } = usePWA();

  if (isOnline) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500/90 backdrop-blur-sm">
      <div className="container mx-auto px-4 py-2">
        <div className="flex items-center justify-center gap-2 text-sm font-medium text-black">
          <WifiOff className="w-4 h-4" />
          <span>You're offline. Some features may be limited.</span>
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-1 ml-2 px-2 py-0.5 rounded bg-black/20 hover:bg-black/30 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}
