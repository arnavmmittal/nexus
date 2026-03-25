'use client';

import { RefreshCw, Sparkles } from 'lucide-react';
import { usePWA } from '@/hooks/pwa';
import { Button } from '@/components/ui/button';

export function UpdatePrompt() {
  const { isUpdateAvailable, update } = usePWA();

  if (!isUpdateAvailable) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 z-50 animate-in slide-in-from-bottom-4 duration-300">
      <div className="glass-panel rounded-xl p-4 shadow-2xl border border-emerald-500/30">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-emerald-500" />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white text-sm">Update Available</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              A new version of Nexus is ready.
            </p>
          </div>
        </div>

        <Button
          size="sm"
          onClick={update}
          className="w-full mt-3 bg-emerald-500 hover:bg-emerald-600 text-black"
        >
          <RefreshCw className="w-4 h-4 mr-1" />
          Update Now
        </Button>
      </div>
    </div>
  );
}
