'use client';

import { useState, useEffect, useCallback } from 'react';
import { Wifi, WifiOff, Thermometer, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------- Types ----------

interface TerminalHealth {
  cpu_temp_c: number | null;
  memory: { percent: number };
  network: {
    connected: boolean;
    wifi_signal_dbm: number | null;
    latency_ms: number | null;
  };
  chromium_running: boolean;
  status: 'healthy' | 'warning' | 'critical';
}

interface TerminalStatusBarProps {
  /** Override health data (e.g. from a parent websocket). Falls back to polling. */
  health?: TerminalHealth | null;
  className?: string;
}

// ---------- Helpers ----------

function getWifiStrength(dbm: number | null): 'strong' | 'medium' | 'weak' | 'none' {
  if (dbm === null) return 'none';
  if (dbm >= -50) return 'strong';
  if (dbm >= -70) return 'medium';
  return 'weak';
}

function getTempStatus(temp: number | null): 'good' | 'warning' | 'critical' {
  if (temp === null) return 'good';
  if (temp >= 80) return 'critical';
  if (temp >= 70) return 'warning';
  return 'good';
}

const STATUS_COLORS = {
  good: 'text-emerald-400',
  warning: 'text-amber-400',
  critical: 'text-red-400',
} as const;

const WIFI_COLORS = {
  strong: 'text-emerald-400',
  medium: 'text-amber-400',
  weak: 'text-red-400',
  none: 'text-white/20',
} as const;

// ---------- Component ----------

export function TerminalStatusBar({ health: externalHealth, className }: TerminalStatusBarProps) {
  const [health, setHealth] = useState<TerminalHealth | null>(externalHealth ?? null);
  const [visible, setVisible] = useState(true);
  const [hideTimeout, setHideTimeout] = useState<NodeJS.Timeout | null>(null);
  const [micActive, setMicActive] = useState(false);
  const [speakerActive, setSpeakerActive] = useState(true);

  // Poll the health monitor if no external data is provided
  useEffect(() => {
    if (externalHealth !== undefined) {
      setHealth(externalHealth);
      return;
    }

    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/health/terminal/status');
        if (res.ok) {
          const data = await res.json();
          setHealth(data);
        }
      } catch {
        // Silently fail - the status bar will show unknown state
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 30_000);
    return () => clearInterval(interval);
  }, [externalHealth]);

  // Check mic status via permissions API
  useEffect(() => {
    if (typeof navigator === 'undefined' || !navigator.permissions) return;

    navigator.permissions.query({ name: 'microphone' as PermissionName }).then((result) => {
      setMicActive(result.state === 'granted');
      result.onchange = () => setMicActive(result.state === 'granted');
    }).catch(() => {
      // Permissions API not available for mic
    });
  }, []);

  // Auto-hide after 5 seconds
  const scheduleHide = useCallback(() => {
    if (hideTimeout) clearTimeout(hideTimeout);
    const timeout = setTimeout(() => setVisible(false), 5_000);
    setHideTimeout(timeout);
  }, [hideTimeout]);

  // Show on mount, schedule auto-hide
  useEffect(() => {
    setVisible(true);
    scheduleHide();
    return () => {
      if (hideTimeout) clearTimeout(hideTimeout);
    };
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tap to show
  const handleTap = useCallback(() => {
    setVisible(true);
    scheduleHide();
  }, [scheduleHide]);

  const wifiStrength = getWifiStrength(health?.network?.wifi_signal_dbm ?? null);
  const tempStatus = getTempStatus(health?.cpu_temp_c ?? null);

  return (
    <div
      onClick={handleTap}
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40',
        'flex items-center justify-center gap-6 px-4 py-2',
        'bg-black/60 backdrop-blur-sm border-t border-white/5',
        'transition-all duration-500 ease-in-out cursor-pointer select-none',
        visible ? 'translate-y-0 opacity-100' : 'translate-y-full opacity-0',
        className,
      )}
    >
      {/* WiFi */}
      <div className="flex items-center gap-1.5" title={
        health?.network?.connected
          ? `WiFi: ${wifiStrength} (${health.network.wifi_signal_dbm ?? '?'} dBm, ${health.network.latency_ms ?? '?'}ms)`
          : 'Network disconnected'
      }>
        {health?.network?.connected ? (
          <Wifi className={cn('h-3.5 w-3.5', WIFI_COLORS[wifiStrength])} />
        ) : (
          <WifiOff className="h-3.5 w-3.5 text-red-400" />
        )}
        <span className={cn('text-[10px] uppercase tracking-widest', WIFI_COLORS[wifiStrength])}>
          {health?.network?.connected ? wifiStrength : 'offline'}
        </span>
      </div>

      {/* Separator */}
      <div className="h-3 w-px bg-white/10" />

      {/* CPU Temperature */}
      <div className="flex items-center gap-1.5" title={
        health?.cpu_temp_c !== null ? `CPU: ${health?.cpu_temp_c?.toFixed(1)}°C` : 'CPU temp: unknown'
      }>
        <Thermometer className={cn('h-3.5 w-3.5', STATUS_COLORS[tempStatus])} />
        <span className={cn('text-[10px] tabular-nums', STATUS_COLORS[tempStatus])}>
          {health?.cpu_temp_c !== null && health?.cpu_temp_c !== undefined
            ? `${health.cpu_temp_c.toFixed(0)}°`
            : '--°'}
        </span>
      </div>

      {/* Separator */}
      <div className="h-3 w-px bg-white/10" />

      {/* Microphone */}
      <div className="flex items-center gap-1.5" title={micActive ? 'Mic: ready' : 'Mic: not available'}>
        {micActive ? (
          <Mic className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <MicOff className="h-3.5 w-3.5 text-white/20" />
        )}
        <span className={cn('text-[10px] uppercase tracking-widest', micActive ? 'text-emerald-400' : 'text-white/20')}>
          mic
        </span>
      </div>

      {/* Separator */}
      <div className="h-3 w-px bg-white/10" />

      {/* Speaker */}
      <div className="flex items-center gap-1.5" title={speakerActive ? 'Speaker: active' : 'Speaker: muted'}>
        {speakerActive ? (
          <Volume2 className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <VolumeX className="h-3.5 w-3.5 text-white/20" />
        )}
        <span className={cn('text-[10px] uppercase tracking-widest', speakerActive ? 'text-emerald-400' : 'text-white/20')}>
          spk
        </span>
      </div>

      {/* Overall status dot */}
      {health && (
        <>
          <div className="h-3 w-px bg-white/10" />
          <div
            className={cn(
              'h-2 w-2 rounded-full',
              health.status === 'healthy' && 'bg-emerald-500',
              health.status === 'warning' && 'bg-amber-500 animate-pulse',
              health.status === 'critical' && 'bg-red-500 animate-pulse',
            )}
            title={`System: ${health.status}`}
          />
        </>
      )}
    </div>
  );
}
