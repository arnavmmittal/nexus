'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { Mic } from 'lucide-react';

// ---------- Types ----------

export type VoiceOrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface VoiceOrbProps {
  /** Current voice state. */
  state: VoiceOrbState;
  /** Normalized audio level 0-1 for reactive animations. */
  audioLevel?: number;
  /** Called when the user taps the orb to activate voice. */
  onActivate?: () => void;
  /** Called when the user taps while listening to deactivate. */
  onDeactivate?: () => void;
  /** Last spoken text to display below the orb. */
  lastText?: string;
  /** Whether the text is from the user or the assistant. */
  lastTextSource?: 'user' | 'assistant';
  className?: string;
}

// State-specific styling
const STATE_CONFIG: Record<VoiceOrbState, {
  label: string;
  ringColor: string;
  glowColor: string;
  bgGradient: string;
  textColor: string;
}> = {
  idle: {
    label: 'Tap to speak',
    ringColor: 'border-blue-500/30',
    glowColor: 'shadow-blue-500/20',
    bgGradient: 'from-blue-600/20 to-blue-900/30',
    textColor: 'text-blue-400',
  },
  listening: {
    label: 'Listening...',
    ringColor: 'border-cyan-400/50',
    glowColor: 'shadow-cyan-400/30',
    bgGradient: 'from-cyan-500/20 to-cyan-900/30',
    textColor: 'text-cyan-400',
  },
  thinking: {
    label: 'Processing...',
    ringColor: 'border-purple-500/40',
    glowColor: 'shadow-purple-500/25',
    bgGradient: 'from-purple-600/20 to-purple-900/30',
    textColor: 'text-purple-400',
  },
  speaking: {
    label: 'Speaking...',
    ringColor: 'border-emerald-400/50',
    glowColor: 'shadow-emerald-400/30',
    bgGradient: 'from-emerald-500/20 to-emerald-900/30',
    textColor: 'text-emerald-400',
  },
};

// ---------- Sub-components ----------

/** Expanding ripple rings for the listening state. */
function ListeningRipples() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="absolute rounded-full border border-cyan-400/30"
          style={{
            width: '100%',
            height: '100%',
            animation: `voiceorb-ripple 2.4s ease-out infinite`,
            animationDelay: `${i * 0.8}s`,
          }}
        />
      ))}
    </div>
  );
}

/** Rotating spinner for the thinking state. */
function ThinkingSpinner() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div
        className="absolute rounded-full border-2 border-transparent border-t-purple-400/60 border-r-purple-400/30"
        style={{
          width: '110%',
          height: '110%',
          animation: 'voiceorb-spin 1.2s linear infinite',
        }}
      />
      <div
        className="absolute rounded-full border-2 border-transparent border-b-purple-300/40 border-l-purple-300/20"
        style={{
          width: '125%',
          height: '125%',
          animation: 'voiceorb-spin 2s linear infinite reverse',
        }}
      />
    </div>
  );
}

/** Gentle pulse overlay for the idle state. */
function IdlePulse() {
  return (
    <div
      className="absolute inset-0 rounded-full bg-blue-500/10 pointer-events-none"
      style={{
        animation: 'voiceorb-idle-pulse 3s ease-in-out infinite',
      }}
    />
  );
}

/** Wave effect for the speaking state. */
function SpeakingWave({ audioLevel }: { audioLevel: number }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div
        className="absolute rounded-full bg-emerald-400/10"
        style={{
          width: `${100 + audioLevel * 30}%`,
          height: `${100 + audioLevel * 30}%`,
          transition: 'width 0.1s ease-out, height 0.1s ease-out',
        }}
      />
      <div
        className="absolute rounded-full border border-emerald-400/20"
        style={{
          width: `${110 + audioLevel * 20}%`,
          height: `${110 + audioLevel * 20}%`,
          animation: 'voiceorb-ripple 1.5s ease-out infinite',
        }}
      />
    </div>
  );
}

// ---------- Main Component ----------

export function VoiceOrb({
  state,
  audioLevel = 0,
  onActivate,
  onDeactivate,
  lastText,
  lastTextSource = 'assistant',
  className,
}: VoiceOrbProps) {
  const config = STATE_CONFIG[state];
  const [mounted, setMounted] = useState(false);
  const orbRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Notify LED controller of state change (for hardware terminal)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Fire-and-forget POST to the local LED controller
    fetch('http://127.0.0.1:8080/led/state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state }),
    }).catch(() => {
      // LED controller not available (not on Pi hardware) - that's fine
    });
  }, [state]);

  const handleTap = useCallback(() => {
    if (state === 'idle') {
      onActivate?.();
    } else if (state === 'listening') {
      onDeactivate?.();
    }
  }, [state, onActivate, onDeactivate]);

  if (!mounted) {
    return (
      <div className={cn('flex flex-col items-center justify-center', className)}>
        <div className="h-48 w-48 rounded-full bg-white/5" />
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col items-center justify-center gap-6', className)}>
      {/* Inject keyframe animations */}
      <style>{`
        @keyframes voiceorb-ripple {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.8); opacity: 0; }
        }
        @keyframes voiceorb-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes voiceorb-idle-pulse {
          0%, 100% { opacity: 0.2; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.05); }
        }
      `}</style>

      {/* The Orb */}
      <div className="relative flex items-center justify-center" style={{ width: 200, height: 200 }}>
        {/* State-specific animations */}
        {state === 'idle' && <IdlePulse />}
        {state === 'listening' && <ListeningRipples />}
        {state === 'thinking' && <ThinkingSpinner />}
        {state === 'speaking' && <SpeakingWave audioLevel={audioLevel} />}

        {/* Ambient glow */}
        <div
          className={cn(
            'absolute inset-0 rounded-full blur-2xl opacity-40 transition-all duration-700',
            config.glowColor,
          )}
          style={{
            background: `radial-gradient(circle, currentColor 0%, transparent 70%)`,
          }}
        />

        {/* Main orb button */}
        <button
          ref={orbRef}
          onClick={handleTap}
          disabled={state === 'thinking' || state === 'speaking'}
          className={cn(
            'relative z-10 flex items-center justify-center',
            'h-48 w-48 rounded-full',
            'bg-gradient-to-br', config.bgGradient,
            'border-2', config.ringColor,
            'shadow-[0_0_60px_-15px]', config.glowColor,
            'transition-all duration-500 ease-out',
            'active:scale-95',
            state === 'idle' && 'hover:scale-105 hover:border-blue-400/50',
            state === 'listening' && 'scale-110',
            (state === 'thinking' || state === 'speaking') && 'cursor-default',
          )}
        >
          {/* Inner gradient overlay */}
          <div className="absolute inset-2 rounded-full bg-gradient-to-b from-white/5 to-transparent" />

          {/* Mic icon */}
          <Mic
            className={cn(
              'relative z-10 h-12 w-12 transition-all duration-500',
              config.textColor,
              state === 'listening' && 'scale-110',
              state === 'thinking' && 'animate-pulse opacity-60',
              state === 'speaking' && 'opacity-50',
            )}
          />

          {/* Audio level ring (listening only) */}
          {state === 'listening' && (
            <svg
              className="absolute inset-0 h-full w-full -rotate-90 pointer-events-none"
              viewBox="0 0 100 100"
            >
              <circle
                cx="50"
                cy="50"
                r="48"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeDasharray={`${audioLevel * 301.6} 301.6`}
                className="text-cyan-400/60 transition-all duration-75"
              />
            </svg>
          )}
        </button>
      </div>

      {/* State label */}
      <p className={cn('text-lg font-medium transition-colors duration-500', config.textColor)}>
        {config.label}
      </p>

      {/* Last spoken text */}
      {lastText && (
        <div className={cn(
          'max-w-md text-center px-6 py-3 rounded-2xl',
          'border border-white/5 bg-white/[0.03]',
          'transition-all duration-300',
        )}>
          <p className="text-[10px] uppercase tracking-widest text-white/30 mb-1">
            {lastTextSource === 'user' ? 'You said' : 'Nexus'}
          </p>
          <p className={cn(
            'text-sm leading-relaxed',
            lastTextSource === 'user' ? 'text-white/70' : 'text-emerald-100/80',
          )}>
            {lastText}
          </p>
        </div>
      )}
    </div>
  );
}
