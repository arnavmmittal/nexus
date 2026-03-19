'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { JarvisOrb } from './JarvisOrb';
import { useVoice, type VoiceState } from './useVoice';
import { cn } from '@/lib/utils';
import { Mic, MicOff, Volume2, X, Minimize2, ChevronUp } from 'lucide-react';

interface JarvisVoiceUIProps {
  onMessage?: (transcript: string) => void;
  onResponse?: (response: string) => Promise<void>;
  className?: string;
}

const stateLabels: Record<VoiceState, string> = {
  idle: 'Ready',
  listening: 'Listening...',
  thinking: 'Processing...',
  speaking: 'Speaking...',
};

const stateColors: Record<VoiceState, string> = {
  idle: 'text-blue-400',
  listening: 'text-cyan-400',
  thinking: 'text-purple-400',
  speaking: 'text-emerald-400',
};

export function JarvisVoiceUI({ onMessage, onResponse, className }: JarvisVoiceUIProps) {
  const {
    state,
    transcript,
    interimTranscript,
    audioLevel,
    startListening,
    stopListening,
    speak,
    isSupported,
  } = useVoice();

  const [isMinimized, setIsMinimized] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [lastResponse, setLastResponse] = useState('');
  const [isHolding, setIsHolding] = useState(false);
  const holdTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Handle push-to-talk
  const handleMouseDown = useCallback(() => {
    if (!isSupported) return;
    setIsHolding(true);
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

      // Simulate AI response (replace with actual API call)
      const processMessage = async () => {
        // Simulated responses
        const responses = [
          `Based on your current goals and patterns, I'd suggest focusing on the Nexus project today. You're in a great flow state.`,
          `I see you have 3 tasks remaining. Your energy levels look optimal for deep work right now.`,
          `Good timing. You've been on a 24-day coding streak. Let me help you maintain that momentum.`,
          `Analyzing your schedule... You have a clear 3-hour block coming up. Perfect for focused development.`,
        ];

        const response = responses[Math.floor(Math.random() * responses.length)];
        setLastResponse(response);

        if (onResponse) {
          await onResponse(response);
        }

        await speak(response);
      };

      processMessage();
    }
  }, [state, transcript, onMessage, onResponse, speak]);

  // Keyboard shortcut (Space to talk)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        if (!isHolding && state === 'idle') {
          handleMouseDown();
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        handleMouseUp();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleMouseDown, handleMouseUp, isHolding, state]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (holdTimeoutRef.current) {
        clearTimeout(holdTimeoutRef.current);
      }
    };
  }, []);

  if (isMinimized) {
    return (
      <button
        onClick={() => setIsMinimized(false)}
        className={cn(
          'fixed bottom-6 right-6 z-50',
          'w-14 h-14 rounded-full',
          'glass-panel border border-white/10',
          'flex items-center justify-center',
          'hover:scale-105 transition-transform',
          'shadow-lg shadow-blue-500/20',
          className
        )}
      >
        <div className="relative">
          <Volume2 className="w-6 h-6 text-blue-400" />
          <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse" />
        </div>
      </button>
    );
  }

  return (
    <div
      className={cn(
        'fixed bottom-6 right-6 z-50',
        'flex flex-col items-center',
        isExpanded ? 'w-80' : 'w-48',
        'transition-all duration-300',
        className
      )}
    >
      {/* Control buttons */}
      <div className="absolute -top-2 right-0 flex gap-1">
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
          'glass-panel rounded-2xl border border-white/10',
          'p-4 backdrop-blur-xl',
          'shadow-2xl shadow-black/50',
          'transition-all duration-300',
          isExpanded ? 'w-full' : 'w-48'
        )}
      >
        {/* The Orb */}
        <div className="flex justify-center">
          <JarvisOrb
            state={state}
            audioLevel={audioLevel}
            size={isExpanded ? 180 : 120}
          />
        </div>

        {/* State indicator */}
        <div className="mt-4 text-center">
          <p className={cn('text-sm font-medium', stateColors[state])}>
            {stateLabels[state]}
          </p>
        </div>

        {/* Transcript display */}
        {(transcript || interimTranscript) && (
          <div className="mt-3 p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-muted-foreground mb-1">You said:</p>
            <p className="text-sm">
              {transcript || <span className="text-muted-foreground">{interimTranscript}</span>}
            </p>
          </div>
        )}

        {/* Last response (expanded view) */}
        {isExpanded && lastResponse && state === 'idle' && (
          <div className="mt-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <p className="text-xs text-emerald-400 mb-1">Nexus:</p>
            <p className="text-sm text-emerald-100">{lastResponse}</p>
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
            'mt-4 w-full py-3 px-4 rounded-xl',
            'flex items-center justify-center gap-2',
            'transition-all duration-200',
            'font-medium text-sm',
            isHolding
              ? 'bg-cyan-500/30 border-2 border-cyan-400 text-cyan-300 scale-95'
              : 'bg-white/5 border border-white/10 text-white/80 hover:bg-white/10',
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
        <p className="mt-2 text-center text-xs text-muted-foreground">
          or hold{' '}
          <kbd className="px-1.5 py-0.5 text-[10px] bg-white/10 rounded border border-white/10">
            Space
          </kbd>
        </p>
      </div>

      {/* Audio level indicator bar */}
      {state === 'listening' && (
        <div className="mt-2 w-32 h-1 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-400 to-cyan-300 transition-all duration-75"
            style={{ width: `${audioLevel * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
