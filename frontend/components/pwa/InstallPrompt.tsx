'use client';

import { useState, useEffect } from 'react';
import { X, Download, Smartphone } from 'lucide-react';
import { usePWA } from '@/hooks/pwa';
import { Button } from '@/components/ui/button';

export function InstallPrompt() {
  const { isInstallable, isStandalone, install, dismissInstall } = usePWA();
  const [isVisible, setIsVisible] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [showIOSInstructions, setShowIOSInstructions] = useState(false);

  useEffect(() => {
    // Detect iOS
    const isIOSDevice = /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as Window & { MSStream?: unknown }).MSStream;
    setIsIOS(isIOSDevice);

    // Check if we should show the prompt
    const dismissed = localStorage.getItem('pwa-install-dismissed');
    const dismissedTime = dismissed ? parseInt(dismissed, 10) : 0;
    const daysSinceDismissed = (Date.now() - dismissedTime) / (1000 * 60 * 60 * 24);

    // Show if not installed and not recently dismissed
    if (!isStandalone && (isInstallable || isIOSDevice) && daysSinceDismissed > 7) {
      // Delay showing the prompt
      const timer = setTimeout(() => {
        setIsVisible(true);
      }, 5000);

      return () => clearTimeout(timer);
    }
  }, [isInstallable, isStandalone]);

  const handleInstall = async () => {
    if (isIOS) {
      setShowIOSInstructions(true);
      return;
    }

    const success = await install();
    if (success) {
      setIsVisible(false);
    }
  };

  const handleDismiss = () => {
    dismissInstall();
    setIsVisible(false);
  };

  if (!isVisible || isStandalone) {
    return null;
  }

  return (
    <>
      {/* Main install prompt */}
      <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50 animate-in slide-in-from-bottom-4 duration-300">
        <div className="glass-panel rounded-xl p-4 shadow-2xl border border-white/10">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center">
              <Smartphone className="w-6 h-6 text-white" />
            </div>

            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-white">Install Nexus</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Add Nexus to your home screen for quick access and offline support.
              </p>

              <div className="flex items-center gap-2 mt-3">
                <Button
                  size="sm"
                  onClick={handleInstall}
                  className="bg-emerald-500 hover:bg-emerald-600 text-black"
                >
                  <Download className="w-4 h-4 mr-1" />
                  {isIOS ? 'How to Install' : 'Install'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleDismiss}
                  className="text-muted-foreground hover:text-white"
                >
                  Not now
                </Button>
              </div>
            </div>

            <button
              onClick={handleDismiss}
              className="p-1 text-muted-foreground hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* iOS Instructions Modal */}
      {showIOSInstructions && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-panel rounded-2xl p-6 max-w-sm w-full animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Install on iOS</h3>
              <button
                onClick={() => setShowIOSInstructions(false)}
                className="p-1 text-muted-foreground hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <ol className="space-y-4 text-sm">
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center text-xs font-semibold">
                  1
                </span>
                <span className="text-muted-foreground">
                  Tap the <strong className="text-white">Share</strong> button at the bottom of Safari
                </span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center text-xs font-semibold">
                  2
                </span>
                <span className="text-muted-foreground">
                  Scroll down and tap <strong className="text-white">Add to Home Screen</strong>
                </span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center text-xs font-semibold">
                  3
                </span>
                <span className="text-muted-foreground">
                  Tap <strong className="text-white">Add</strong> in the top right corner
                </span>
              </li>
            </ol>

            <Button
              className="w-full mt-6 bg-emerald-500 hover:bg-emerald-600 text-black"
              onClick={() => setShowIOSInstructions(false)}
            >
              Got it
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
