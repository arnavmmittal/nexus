'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import api from '@/lib/api';

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

export interface UseVoiceOptions {
  useElevenLabs?: boolean;
  voiceId?: string;
  persona?: 'jarvis' | 'tars';
  continuous?: boolean;           // Keep listening after processing
  silenceTimeout?: number;        // Ms of silence before auto-stop (default 1500)
  playbackSpeed?: number;         // Speech playback speed (default 1.15 for Jarvis)
}

export interface UseVoiceReturn {
  state: VoiceState;
  transcript: string;
  interimTranscript: string;
  audioLevel: number;
  startListening: () => void;
  stopListening: () => void;
  stopSpeaking: () => void;       // Interrupt current speech
  speak: (text: string) => Promise<void>;
  speakWithAI: (text: string) => Promise<string>;
  getAudioData: () => Float32Array | null;
  isSupported: boolean;
  isElevenLabsEnabled: boolean;
}

export function useVoice(options?: UseVoiceOptions): UseVoiceReturn {
  const {
    useElevenLabs = true,
    voiceId,
    persona = 'jarvis',
    continuous = false,
    silenceTimeout = 1500,
    playbackSpeed = persona === 'jarvis' ? 1.15 : 1.0,
  } = options || {};

  const [state, setState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [isSupported, setIsSupported] = useState(true);
  const [isElevenLabsEnabled, setIsElevenLabsEnabled] = useState(false);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioDataRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  const silenceTimeoutIdRef = useRef<NodeJS.Timeout | null>(null);
  const lastSpeechTimeRef = useRef<number>(Date.now());
  const speakingAnimationFrameRef = useRef<number | null>(null);
  const continuousModeRef = useRef<boolean>(continuous);

  // Check for browser support and ElevenLabs status
  useEffect(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      setIsSupported(false);
      console.warn('Speech Recognition API not supported in this browser');
    }

    // Check ElevenLabs status
    if (useElevenLabs) {
      api.getVoiceStatus().then((status) => {
        setIsElevenLabsEnabled(status.status === 'operational');
      }).catch(() => {
        setIsElevenLabsEnabled(false);
      });
    }
  }, [useElevenLabs]);

  // Initialize audio context for visualization
  const initAudioContext = useCallback(async () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      if (!analyserRef.current) {
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 256;
        analyserRef.current.smoothingTimeConstant = 0.8;
        audioDataRef.current = new Float32Array(analyserRef.current.frequencyBinCount);
      }

      // Get microphone stream for audio visualization while listening
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);
      sourceRef.current.connect(analyserRef.current);

      // Start monitoring audio levels
      const updateAudioLevel = () => {
        if (analyserRef.current && audioDataRef.current) {
          analyserRef.current.getFloatFrequencyData(audioDataRef.current);
          // Calculate average level from frequency data
          const sum = audioDataRef.current.reduce((acc, val) => acc + val, 0);
          const avg = sum / audioDataRef.current.length;
          // Normalize to 0-1 range (frequency data is in dB, typically -100 to 0)
          const normalized = Math.max(0, Math.min(1, (avg + 100) / 100));
          setAudioLevel(normalized);
        }
        animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
      };
      updateAudioLevel();
    } catch (error) {
      console.error('Failed to initialize audio context:', error);
    }
  }, []);

  // Cleanup audio context
  const cleanupAudioContext = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // Clear silence timeout
  const clearSilenceTimeout = useCallback(() => {
    if (silenceTimeoutIdRef.current) {
      clearTimeout(silenceTimeoutIdRef.current);
      silenceTimeoutIdRef.current = null;
    }
  }, []);

  // Reset silence timeout (called when speech is detected)
  const resetSilenceTimeout = useCallback(() => {
    clearSilenceTimeout();
    lastSpeechTimeRef.current = Date.now();

    if (continuous) {
      silenceTimeoutIdRef.current = setTimeout(() => {
        // User has been silent for silenceTimeout ms, stop listening
        if (recognitionRef.current && state === 'listening') {
          recognitionRef.current.stop();
        }
      }, silenceTimeout);
    }
  }, [continuous, silenceTimeout, clearSilenceTimeout, state]);

  // Stop current speech (interrupt) - defined early so startListening can use it
  const stopSpeaking = useCallback(() => {
    // Stop ElevenLabs audio
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
      audioElementRef.current = null;
    }

    // Stop Web Speech API
    if (typeof speechSynthesis !== 'undefined') {
      speechSynthesis.cancel();
    }

    // Cancel any speaking animation
    if (speakingAnimationFrameRef.current) {
      cancelAnimationFrame(speakingAnimationFrameRef.current);
      speakingAnimationFrameRef.current = null;
    }

    setAudioLevel(0);
    setState('idle');
  }, []);

  // Start listening for voice input
  const startListening = useCallback(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      console.error('Speech Recognition not supported');
      return;
    }

    // If we're speaking, interrupt first
    if (state === 'speaking') {
      stopSpeaking();
    }

    // Clean up any existing recognition
    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }
    clearSilenceTimeout();

    const recognition = new SpeechRecognitionAPI();
    // Use continuous mode for voice-activated, but we'll manage when to stop
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setState('listening');
      setTranscript('');
      setInterimTranscript('');
      initAudioContext();
      if (continuous) {
        // Start silence detection
        resetSilenceTimeout();
      }
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }

      // Reset silence timeout whenever we get speech
      if (continuous && (finalTranscript || interimText)) {
        resetSilenceTimeout();
      }

      if (finalTranscript) {
        setTranscript((prev) => prev + finalTranscript);
        setInterimTranscript('');
      } else {
        setInterimTranscript(interimText);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // Ignore no-speech errors in continuous mode
      if (event.error === 'no-speech' && continuous) {
        return;
      }
      console.error('Speech recognition error:', event.error);
      setState('idle');
      cleanupAudioContext();
      clearSilenceTimeout();
    };

    recognition.onend = () => {
      clearSilenceTimeout();
      // Only go to idle if we're not transitioning to thinking/speaking
      if (state === 'listening') {
        setState('idle');
      }
      cleanupAudioContext();
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
    }
  }, [initAudioContext, cleanupAudioContext, state, continuous, resetSilenceTimeout, clearSilenceTimeout, stopSpeaking]);

  // Stop listening
  const stopListening = useCallback(() => {
    clearSilenceTimeout();
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    cleanupAudioContext();
    // If we have a transcript, transition to thinking
    if (transcript || interimTranscript) {
      setTranscript(transcript || interimTranscript);
      setInterimTranscript('');
      setState('thinking');
    } else {
      setState('idle');
    }
  }, [cleanupAudioContext, transcript, interimTranscript, clearSilenceTimeout]);

  // Speak text using ElevenLabs or Web Speech API
  const speak = useCallback(async (text: string): Promise<void> => {
    setState('speaking');

    // Try ElevenLabs first if enabled
    if (useElevenLabs && isElevenLabsEnabled) {
      try {
        const response = await api.synthesizeSpeech({
          text,
          voice_id: voiceId,
        });

        // Play the audio stream
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        return new Promise((resolve) => {
          const audio = new Audio(audioUrl);
          audio.playbackRate = playbackSpeed;
          audioElementRef.current = audio;

          // Simple speaking animation
          let speakingAnimationFrame: number;
          const animateSpeaking = () => {
            const time = Date.now() / 100;
            const level = 0.5 + 0.3 * Math.sin(time) + 0.1 * Math.sin(time * 2.5);
            setAudioLevel(level);
            speakingAnimationFrame = requestAnimationFrame(animateSpeaking);
          };

          audio.onplay = () => {
            animateSpeaking();
          };

          audio.onended = () => {
            cancelAnimationFrame(speakingAnimationFrame);
            setAudioLevel(0);
            setState('idle');
            URL.revokeObjectURL(audioUrl);
            resolve();
          };

          audio.onerror = () => {
            cancelAnimationFrame(speakingAnimationFrame);
            setAudioLevel(0);
            setState('idle');
            URL.revokeObjectURL(audioUrl);
            resolve();
          };

          audio.play().catch((error) => {
            console.error('Failed to play audio:', error);
            // Fall back to Web Speech API
            fallbackToWebSpeech(text).then(resolve);
          });
        });
      } catch (error) {
        console.error('ElevenLabs synthesis failed:', error);
        // Fall back to Web Speech API
        return fallbackToWebSpeech(text);
      }
    }

    // Use Web Speech API
    return fallbackToWebSpeech(text);
  }, [useElevenLabs, isElevenLabsEnabled, voiceId, playbackSpeed]);

  // Fallback to Web Speech API
  const fallbackToWebSpeech = useCallback((text: string): Promise<void> => {
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      // Try to find a suitable voice
      const voices = speechSynthesis.getVoices();
      const preferredVoice = voices.find(
        (voice) =>
          voice.name.includes('Daniel') ||
          voice.name.includes('Google UK English Male') ||
          voice.lang.startsWith('en-GB')
      );
      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      // Simple speaking animation
      let speakingAnimationFrame: number;
      const animateSpeaking = () => {
        const time = Date.now() / 100;
        const level = 0.5 + 0.3 * Math.sin(time) + 0.1 * Math.sin(time * 2.5);
        setAudioLevel(level);
        speakingAnimationFrame = requestAnimationFrame(animateSpeaking);
      };

      utterance.onstart = () => {
        animateSpeaking();
      };

      utterance.onend = () => {
        cancelAnimationFrame(speakingAnimationFrame);
        setAudioLevel(0);
        setState('idle');
        resolve();
      };

      utterance.onerror = () => {
        cancelAnimationFrame(speakingAnimationFrame);
        setAudioLevel(0);
        setState('idle');
        resolve();
      };

      speechSynthesis.speak(utterance);
    });
  }, []);

  // Voice chat with AI - sends text, gets AI response, plays audio
  const speakWithAI = useCallback(async (text: string): Promise<string> => {
    setState('thinking');

    try {
      if (useElevenLabs && isElevenLabsEnabled) {
        // Use the voice chat endpoint that returns audio
        const response = await api.voiceChat({
          text,
          conversation_id: conversationIdRef.current || undefined,
          voice_id: voiceId,
          persona,
        });

        // Get text response from header
        const textResponse = response.headers.get('X-Text-Response') || '';
        const newConversationId = response.headers.get('X-Conversation-Id');
        if (newConversationId) {
          conversationIdRef.current = newConversationId;
        }

        // Play the audio
        setState('speaking');
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        await new Promise<void>((resolve) => {
          const audio = new Audio(audioUrl);
          audio.playbackRate = playbackSpeed;
          audioElementRef.current = audio;

          const animateSpeaking = () => {
            const time = Date.now() / 100;
            const level = 0.5 + 0.3 * Math.sin(time) + 0.1 * Math.sin(time * 2.5);
            setAudioLevel(level);
            speakingAnimationFrameRef.current = requestAnimationFrame(animateSpeaking);
          };

          audio.onplay = () => {
            animateSpeaking();
          };

          audio.onended = () => {
            if (speakingAnimationFrameRef.current) {
              cancelAnimationFrame(speakingAnimationFrameRef.current);
              speakingAnimationFrameRef.current = null;
            }
            setAudioLevel(0);
            setState('idle');
            URL.revokeObjectURL(audioUrl);
            resolve();
          };

          audio.onerror = () => {
            if (speakingAnimationFrameRef.current) {
              cancelAnimationFrame(speakingAnimationFrameRef.current);
              speakingAnimationFrameRef.current = null;
            }
            setAudioLevel(0);
            setState('idle');
            URL.revokeObjectURL(audioUrl);
            resolve();
          };

          audio.play().catch((error) => {
            console.error('Failed to play audio:', error);
            resolve();
          });
        });

        return textResponse;
      } else {
        // Get text-only response and use Web Speech API
        const response = await api.voiceChatText({
          text,
          conversation_id: conversationIdRef.current || undefined,
        });

        conversationIdRef.current = response.conversation_id;

        // Speak the response
        await speak(response.text_response);

        return response.text_response;
      }
    } catch (error) {
      console.error('Voice chat error:', error);
      setState('idle');
      throw error;
    }
  }, [useElevenLabs, isElevenLabsEnabled, voiceId, persona, speak, playbackSpeed]);

  // Get current audio frequency data for visualization
  const getAudioData = useCallback((): Float32Array | null => {
    if (analyserRef.current && audioDataRef.current) {
      analyserRef.current.getFloatFrequencyData(audioDataRef.current);
      return audioDataRef.current;
    }
    return null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      if (audioElementRef.current) {
        audioElementRef.current.pause();
      }
      if (silenceTimeoutIdRef.current) {
        clearTimeout(silenceTimeoutIdRef.current);
      }
      if (speakingAnimationFrameRef.current) {
        cancelAnimationFrame(speakingAnimationFrameRef.current);
      }
      cleanupAudioContext();
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [cleanupAudioContext]);

  return {
    state,
    transcript,
    interimTranscript,
    audioLevel,
    startListening,
    stopListening,
    stopSpeaking,
    speak,
    speakWithAI,
    getAudioData,
    isSupported,
    isElevenLabsEnabled,
  };
}
