'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useIntegrationsStatus,
  useGoogleAuth,
  useGitHub,
  usePlaidIntegration,
} from '@/hooks/useIntegrations';
import {
  Calendar,
  Github,
  Building2,
  Link2,
  Link2Off,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  DollarSign,
  CreditCard,
  AlertCircle,
  Eye,
  EyeOff,
} from 'lucide-react';

interface IntegrationCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  status: 'connected' | 'not_connected' | 'error';
  statusText?: string;
  children: React.ReactNode;
}

function IntegrationCard({ icon, title, description, status, statusText, children }: IntegrationCardProps) {
  return (
    <Card className="glass-panel border-white/10">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
              {icon}
            </div>
            <div>
              <CardTitle className="text-base font-semibold">{title}</CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-0.5">
                {description}
              </CardDescription>
            </div>
          </div>
          <Badge
            variant={status === 'connected' ? 'default' : 'secondary'}
            className={cn(
              'h-6 px-2',
              status === 'connected' && 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
              status === 'not_connected' && 'bg-white/5 text-muted-foreground border-white/10',
              status === 'error' && 'bg-red-500/20 text-red-400 border-red-500/30'
            )}
          >
            {status === 'connected' && <CheckCircle2 className="h-3 w-3 mr-1" />}
            {status === 'not_connected' && <XCircle className="h-3 w-3 mr-1" />}
            {status === 'error' && <AlertCircle className="h-3 w-3 mr-1" />}
            {statusText || (status === 'connected' ? 'Connected' : status === 'error' ? 'Error' : 'Not Connected')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function GoogleCalendarIntegration() {
  const { data: status, isLoading } = useIntegrationsStatus();
  const { connect, disconnect, isConnecting, isDisconnecting } = useGoogleAuth();

  const googleStatus = status?.google_calendar;
  const isConnected = googleStatus?.status === 'connected';

  if (isLoading) {
    return (
      <IntegrationCard
        icon={<Calendar className="h-5 w-5 text-blue-400" />}
        title="Google Calendar"
        description="Sync your calendar events and schedule"
        status="not_connected"
      >
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </IntegrationCard>
    );
  }

  return (
    <IntegrationCard
      icon={<Calendar className="h-5 w-5 text-blue-400" />}
      title="Google Calendar"
      description="Sync your calendar events and schedule"
      status={isConnected ? 'connected' : 'not_connected'}
    >
      {isConnected ? (
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-muted-foreground mb-1">Connected Account</p>
            <p className="text-sm font-medium">{googleStatus?.email || 'Unknown'}</p>
            {googleStatus?.connected_at && (
              <p className="text-xs text-muted-foreground mt-1">
                Connected {new Date(googleStatus.connected_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => disconnect()}
            disabled={isDisconnecting}
            className="w-full border-red-500/20 text-red-400 hover:bg-red-500/10"
          >
            {isDisconnecting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Link2Off className="h-4 w-4 mr-2" />
            )}
            Disconnect
          </Button>
        </div>
      ) : (
        <Button
          onClick={() => connect()}
          disabled={isConnecting}
          className="w-full bg-blue-600 hover:bg-blue-700"
        >
          {isConnecting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Link2 className="h-4 w-4 mr-2" />
          )}
          Connect Google Calendar
        </Button>
      )}
    </IntegrationCard>
  );
}

function GitHubIntegration() {
  const { data: status, isLoading } = useIntegrationsStatus();
  const { connect, disconnect, sync, isConnecting, isDisconnecting, isSyncing } = useGitHub();
  const [token, setToken] = useState('');
  const [showToken, setShowToken] = useState(false);

  const githubStatus = status?.github;
  const isConnected = githubStatus?.status === 'connected';

  const handleConnect = () => {
    if (token.trim()) {
      connect(token.trim());
      setToken('');
    }
  };

  if (isLoading) {
    return (
      <IntegrationCard
        icon={<Github className="h-5 w-5 text-white" />}
        title="GitHub"
        description="Track your coding activity and repositories"
        status="not_connected"
      >
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </IntegrationCard>
    );
  }

  return (
    <IntegrationCard
      icon={<Github className="h-5 w-5 text-white" />}
      title="GitHub"
      description="Track your coding activity and repositories"
      status={isConnected ? 'connected' : 'not_connected'}
    >
      {isConnected ? (
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-muted-foreground mb-1">Connected Account</p>
            <p className="text-sm font-medium">@{githubStatus?.username || 'Unknown'}</p>
            {githubStatus?.last_synced && (
              <p className="text-xs text-muted-foreground mt-1">
                Last synced {new Date(githubStatus.last_synced).toLocaleString()}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => sync()}
              disabled={isSyncing}
              className="flex-1"
            >
              {isSyncing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Sync Now
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => disconnect()}
              disabled={isDisconnecting}
              className="flex-1 border-red-500/20 text-red-400 hover:bg-red-500/10"
            >
              {isDisconnecting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Link2Off className="h-4 w-4 mr-2" />
              )}
              Disconnect
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="relative">
            <Input
              type={showToken ? 'text' : 'password'}
              placeholder="Enter Personal Access Token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="pr-10 bg-white/5 border-white/10"
            />
            <button
              type="button"
              onClick={() => setShowToken(!showToken)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <Button
            onClick={handleConnect}
            disabled={isConnecting || !token.trim()}
            className="w-full"
          >
            {isConnecting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Link2 className="h-4 w-4 mr-2" />
            )}
            Connect GitHub
          </Button>
          <p className="text-xs text-muted-foreground">
            Create a token at{' '}
            <a
              href="https://github.com/settings/tokens"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              GitHub Settings
            </a>
          </p>
        </div>
      )}
    </IntegrationCard>
  );
}

function PlaidIntegration() {
  const { data: status, isLoading } = useIntegrationsStatus();
  const { openPlaidLink, disconnectAccount, isLoading: isPlaidLoading, isDisconnecting } = usePlaidIntegration();

  const plaidStatus = status?.plaid;
  const accounts = plaidStatus?.accounts || [];
  const isConnected = accounts.length > 0;

  const formatBalance = (amount?: number) => {
    if (amount === undefined || amount === null) return '--';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const getAccountIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'depository':
        return <Building2 className="h-4 w-4 text-blue-400" />;
      case 'credit':
        return <CreditCard className="h-4 w-4 text-orange-400" />;
      case 'investment':
        return <DollarSign className="h-4 w-4 text-emerald-400" />;
      default:
        return <Building2 className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (isLoading) {
    return (
      <IntegrationCard
        icon={<Building2 className="h-5 w-5 text-emerald-400" />}
        title="Plaid (Banks & Investments)"
        description="Connect bank accounts and track finances"
        status="not_connected"
      >
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </IntegrationCard>
    );
  }

  return (
    <IntegrationCard
      icon={<Building2 className="h-5 w-5 text-emerald-400" />}
      title="Plaid (Banks & Investments)"
      description="Connect bank accounts and track finances"
      status={isConnected ? 'connected' : 'not_connected'}
      statusText={isConnected ? `${accounts.length} account${accounts.length !== 1 ? 's' : ''}` : undefined}
    >
      <div className="space-y-4">
        {accounts.length > 0 && (
          <div className="space-y-2">
            {accounts.map((account) => (
              <div
                key={account.id}
                className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10"
              >
                <div className="flex items-center gap-3">
                  {getAccountIcon(account.type)}
                  <div>
                    <p className="text-sm font-medium">{account.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {account.institution_name}
                      {account.mask && ` - ${account.mask}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-sm font-mono font-medium">
                      {formatBalance(account.current_balance)}
                    </p>
                    {account.available_balance !== account.current_balance && (
                      <p className="text-xs text-muted-foreground">
                        Available: {formatBalance(account.available_balance)}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => disconnectAccount(account.id)}
                    disabled={isDisconnecting}
                    className="text-muted-foreground hover:text-red-400"
                  >
                    {isDisconnecting ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        <Button
          onClick={() => openPlaidLink()}
          disabled={isPlaidLoading}
          variant={isConnected ? 'outline' : 'default'}
          className={cn(
            'w-full',
            !isConnected && 'bg-emerald-600 hover:bg-emerald-700'
          )}
        >
          {isPlaidLoading ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Link2 className="h-4 w-4 mr-2" />
          )}
          {isConnected ? 'Connect Another Account' : 'Connect Bank Account'}
        </Button>

        {!isConnected && (
          <p className="text-xs text-muted-foreground text-center">
            Securely connect via Plaid. Your credentials are never stored.
          </p>
        )}
      </div>
    </IntegrationCard>
  );
}

export function IntegrationsPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Integrations</h2>
        <p className="text-sm text-muted-foreground">
          Connect your accounts to enable automatic data sync and tracking.
        </p>
      </div>

      <div className="grid gap-4">
        <GoogleCalendarIntegration />
        <GitHubIntegration />
        <PlaidIntegration />
      </div>
    </div>
  );
}
