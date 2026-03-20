'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { TarsMonolith } from './TarsMonolith';
import { useVoice, type VoiceState } from '../jarvis/useVoice';
import { cn } from '@/lib/utils';
import { Mic, MicOff, Minimize2, ChevronUp, Maximize2 } from 'lucide-react';
import Link from 'next/link';

interface TarsVoiceUIProps {
  onMessage?: (transcript: string) => void;
  onResponse?: (response: string) => Promise<void>;
  className?: string;
}

const stateLabels: Record<VoiceState, string> = {
  idle: 'TARS Online',
  listening: 'Listening...',
  thinking: 'Processing...',
  speaking: 'Speaking...',
};

const stateColors: Record<VoiceState, string> = {
  idle: 'text-amber-400',
  listening: 'text-cyan-400',
  thinking: 'text-purple-400',
  speaking: 'text-amber-400',
};

export function TarsVoiceUI({ onMessage, onResponse, className }: TarsVoiceUIProps) {
  const {
    state,
    transcript,
    interimTranscript,
    audioLevel,
    startListening,
    stopListening,
    speakWithAI,
    isSupported,
    isElevenLabsEnabled,
  } = useVoice({ useElevenLabs: true, persona: 'tars' });

  const [isMinimized, setIsMinimized] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [lastResponse, setLastResponse] = useState('');
  const [isHolding, setIsHolding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle push-to-talk
  const handleMouseDown = useCallback(() => {
    if (!isSupported) return;
    setIsHolding(true);
    setError(null);
    startListening();
  }, [startListening, isSupported]);

  const handleMouseUp = useCallback(async () => {
    if (!isHolding) return;
    setIsHolding(false);
    stopListening();
  }, [stopListening, isHolding]);

  // Process transcript when listening stops
  useEffect(() => {
    if (state === 'thinking' && transcript) {
      onMessage?.(transcript);

      const processMessage = async () => {
        try {
          // Add TARS personality prefix to get TARS-like responses
          const tarsPrompt = `[Respond as TARS from Interstellar - dry wit, humor setting at 75%, helpful but with occasional sarcasm] ${transcript}`;
          const response = await speakWithAI(tarsPrompt);
          setLastResponse(response);

          if (onResponse) {
            await onResponse(response);
          }
        } catch (err) {
          console.error('TARS voice chat error:', err);
          setError(err instanceof Error ? err.message : 'Failed to process');
        }
      };

      processMessage();
    }
  }, [state, transcript, onMessage, onResponse, speakWithAI]);

  // Cleanup
  useEffect(() => {
    return () => {
      // Cleanup if needed
    };
  }, []);

  if (isMinimized) {
    return (
      <button
        onClick={() => setIsMinimized(false)}
        className={cn(
          'fixed bottom-6 left-6 z-50',
          'w-14 h-14 rounded-lg',
          'glass-panel border border-amber-500/20',
          'flex items-center justify-center',
          'hover:scale-105 transition-transform',
          'shadow-lg shadow-amber-500/10',
          className
        )}
      >
        <div className="w-6 h-8 bg-gradient-to-b from-gray-500 to-gray-600 rounded-sm border border-gray-400/50">
          <div className="w-full h-1 mt-2 bg-amber-400/80" />
        </div>
      </button>
    );
  }

  return (
    <div
      className={cn(
        'fixed bottom-6 left-6 z-50',
        'flex flex-col items-center',
        isExpanded ? 'w-80' : 'w-48',
        'transition-all duration-300',
        className
      )}
    >
      {/* Control buttons */}
      <div className="absolute -top-2 right-0 flex gap-1">
        <Link
          href="/tars"
          className="w-6 h-6 rounded-md glass-panel border border-white/10 flex items-center justify-center hover:bg-white/5"
          title="Full screen mode"
        >
          <Maximize2 className="w-3 h-3 text-muted-foreground" />
        </Link>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-6 h-6 rounded-md glass-panel border border-white/10 flex items-center justify-center hover:bg-white/5"
        >
          <ChevronUp
            className={cn(
              'w-3 h-3 text-muted-foreground transition-transform',
              isExpanded && 'rotate-180'
            )}
          />
        </button>
        <button
          onClick={() => setIsMinimized(true)}
          className="w-6 h-6 rounded-md glass-panel border border-white/10 flex items-center justify-center hover:bg-white/5"
        >
          <Minimize2 className="w-3 h-3 text-muted-foreground" />
        </button>
      </div>

      {/* Main container */}
      <div
        className={cn(
          'glass-panel rounded-2xl border border-amber-500/20',
          'p-4 backdrop-blur-xl',
          'shadow-2xl shadow-black/50',
          'transition-all duration-300',
          isExpanded ? 'w-full' : 'w-48'
        )}
      >
        {/* TARS label */}
        <div className="flex items-center justify-center gap-2 mb-2">
          <span className="text-xs font-mono text-amber-400">TARS</span>
          <span className="text-xs text-gray-500">|</span>
          <span className="text-xs text-gray-400">Humor: 75%</span>
        </div>

        {/* The Monolith */}
        <div className="flex justify-center">
          <TarsMonolith
            state={state}
            audioLevel={audioLevel}
            size={isExpanded ? 180 : 120}
          />
        </div>

        {/* State indicator */}
        <div className="mt-4 text-center">
          <p className={cn('text-sm font-medium font-mono', stateColors[state])}>
            {stateLabels[state]}
          </p>
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}

        {/* Transcript display */}
        {(transcript || interimTranscript) && (
          <div className="mt-3 p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-muted-foreground mb-1">Input:</p>
            <p className="text-sm font-mono">
              {transcript || <span className="text-muted-foreground">{interimTranscript}</span>}
            </p>
          </div>
        )}

        {/* Last response (expanded view) */}
        {isExpanded && lastResponse && state === 'idle' && (
          <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <p className="text-xs text-amber-400 mb-1">TARS:</p>
            <p className="text-sm text-amber-100 font-mono">{lastResponse}</p>
          </div>
        )}

        {/* Push-to-talk button */}
        <button
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onTouchStart={handleMouseDown}
          onTouchEnd={handleMouseUp}
          disabled={!isSupported || state === 'thinking' || state === 'speaking'}
          className={cn(
            'mt-4 w-full py-3 px-4 rounded-lg',
            'flex items-center justify-center gap-2',
            'transition-all duration-200',
            'font-mono text-sm',
            isHolding
              ? 'bg-amber-500/30 border-2 border-amber-400 text-amber-300 scale-95'
              : 'bg-white/5 border border-amber-500/30 text-white/80 hover:bg-white/10',
            (state === 'thinking' || state === 'speaking') && 'opacity-50 cursor-not-allowed',
            !isSupported && 'opacity-50 cursor-not-allowed'
          )}
        >
          {!isSupported ? (
            <>
              <MicOff className="w-4 h-4" />
              <span>Not Supported</span>
            </>
          ) : isHolding ? (
            <>
              <Mic className="w-4 h-4 animate-pulse" />
              <span>Release to send</span>
            </>
          ) : (
            <>
              <Mic className="w-4 h-4" />
              <span>Hold to speak</span>
            </>
          )}
        </button>

        {/* Keyboard hint */}
        <p className="mt-2 text-center text-xs text-muted-foreground font-mono">
          Absolute honesty isn't always the most diplomatic...
        </p>
      </div>

      {/* Audio level indicator */}
      {state === 'listening' && (
        <div className="mt-2 w-32 h-1 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-amber-400 to-amber-300 transition-all duration-75"
            style={{ width: `${audioLevel * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
