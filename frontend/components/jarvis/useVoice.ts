'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

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

export interface UseVoiceReturn {
  state: VoiceState;
  transcript: string;
  interimTranscript: string;
  audioLevel: number;
  startListening: () => void;
  stopListening: () => void;
  speak: (text: string) => Promise<void>;
  getAudioData: () => Float32Array | null;
  isSupported: boolean;
}

export function useVoice(): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>('idle');
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [isSupported, setIsSupported] = useState(true);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioDataRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Check for browser support
  useEffect(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      setIsSupported(false);
      console.warn('Speech Recognition API not supported in this browser');
    }
  }, []);

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

  // Start listening for voice input
  const startListening = useCallback(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      console.error('Speech Recognition not supported');
      return;
    }

    // Clean up any existing recognition
    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setState('listening');
      setTranscript('');
      setInterimTranscript('');
      initAudioContext();
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

      if (finalTranscript) {
        setTranscript(finalTranscript);
        setInterimTranscript('');
      } else {
        setInterimTranscript(interimText);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('Speech recognition error:', event.error);
      setState('idle');
      cleanupAudioContext();
    };

    recognition.onend = () => {
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
  }, [initAudioContext, cleanupAudioContext, state]);

  // Stop listening
  const stopListening = useCallback(() => {
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
  }, [cleanupAudioContext, transcript, interimTranscript]);

  // Speak text using Web Speech API or ElevenLabs
  const speak = useCallback(async (text: string): Promise<void> => {
    setState('speaking');

    return new Promise((resolve) => {
      // Use Web Speech API for now (can be replaced with ElevenLabs)
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

      // Initialize audio context for speaking visualization
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      // Create a simple oscillating audio level for speaking animation
      // In a real implementation, this would be connected to the actual audio output
      let speakingAnimationFrame: number;
      const animateSpeaking = () => {
        // Simulate audio level with sinusoidal motion
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
    speak,
    getAudioData,
    isSupported,
  };
}
