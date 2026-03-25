'use client';

import { Bell, BellOff, BellRing, Loader2, CheckCircle } from 'lucide-react';
import { useNotifications } from '@/hooks/pwa';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface NotificationSettingsProps {
  showTestButton?: boolean;
}

export function NotificationSettings({ showTestButton = false }: NotificationSettingsProps) {
  const {
    status,
    isSubscribed,
    isLoading,
    subscribe,
    unsubscribe,
    sendTestNotification,
  } = useNotifications();

  const [testSent, setTestSent] = useState(false);

  const handleToggle = async () => {
    if (isSubscribed) {
      await unsubscribe();
    } else {
      await subscribe();
    }
  };

  const handleTest = async () => {
    const success = await sendTestNotification();
    if (success) {
      setTestSent(true);
      setTimeout(() => setTestSent(false), 3000);
    }
  };

  if (status === 'unsupported') {
    return (
      <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
        <BellOff className="w-5 h-5 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Notifications not supported</p>
          <p className="text-xs text-muted-foreground">
            Your browser doesn't support push notifications.
          </p>
        </div>
      </div>
    );
  }

  if (status === 'denied') {
    return (
      <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
        <BellOff className="w-5 h-5 text-destructive" />
        <div>
          <p className="text-sm font-medium text-destructive">Notifications blocked</p>
          <p className="text-xs text-muted-foreground">
            Enable notifications in your browser settings to receive alerts from Jarvis.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
        <div className="flex items-center gap-3">
          {isSubscribed ? (
            <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <BellRing className="w-5 h-5 text-emerald-500" />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
              <Bell className="w-5 h-5 text-muted-foreground" />
            </div>
          )}
          <div>
            <p className="text-sm font-medium">
              {isSubscribed ? 'Notifications enabled' : 'Push notifications'}
            </p>
            <p className="text-xs text-muted-foreground">
              {isSubscribed
                ? 'Jarvis can send you alerts even when the app is closed.'
                : 'Get proactive alerts and reminders from Jarvis.'}
            </p>
          </div>
        </div>

        <Button
          variant={isSubscribed ? 'outline' : 'default'}
          size="sm"
          onClick={handleToggle}
          disabled={isLoading}
          className={isSubscribed ? '' : 'bg-emerald-500 hover:bg-emerald-600 text-black'}
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : isSubscribed ? (
            'Disable'
          ) : (
            'Enable'
          )}
        </Button>
      </div>

      {showTestButton && isSubscribed && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={isLoading || testSent}
            className="gap-2"
          >
            {testSent ? (
              <>
                <CheckCircle className="w-4 h-4 text-emerald-500" />
                Sent!
              </>
            ) : (
              <>
                <Bell className="w-4 h-4" />
                Send Test Notification
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
