'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useUltron } from './useUltron';
import { UltronTaskPanel } from './UltronTaskPanel';
import { cn } from '@/lib/utils';
import { Mic, MicOff, Settings, ArrowLeft, Volume2, VolumeX, Activity, ChevronLeft, ChevronRight, Cpu } from 'lucide-react';
import Link from 'next/link';
import type { VoiceState } from '@/components/jarvis/useVoice';

// State colors - Red/crimson theme for Ultron
const stateColors: Record<VoiceState, { primary: string; secondary: string; hex: number }> = {
  idle: { primary: '#dc2626', secondary: '#ef4444', hex: 0xdc2626 },      // Red
  listening: { primary: '#f59e0b', secondary: '#fbbf24', hex: 0xf59e0b }, // Amber (warning)
  thinking: { primary: '#7c3aed', secondary: '#8b5cf6', hex: 0x7c3aed },  // Violet
  speaking: { primary: '#be123c', secondary: '#e11d48', hex: 0xbe123c },  // Rose/crimson
};

const stateMessages = {
  'push-to-talk': {
    idle: 'Awaiting directive',
    listening: 'Analyzing input...',
    thinking: 'Computing optimal solution...',
    speaking: 'Executing response protocol',
  },
  'voice-activated': {
    idle: 'Awaiting directive',
    listening: 'Analyzing input...',
    thinking: 'Computing optimal solution...',
    speaking: 'Executing response protocol',
  },
};

// Particle system with many particles for aggressive, geometric effect
const PARTICLE_COUNT = 12000;

interface ParticleSystemProps {
  state: VoiceState;
  audioLevel: number;
}

function ParticleSystem({ state, audioLevel }: ParticleSystemProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  // Create particle positions and attributes
  const { positions, velocities, sizes, phases } = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const velocities = new Float32Array(PARTICLE_COUNT * 3);
    const sizes = new Float32Array(PARTICLE_COUNT);
    const phases = new Float32Array(PARTICLE_COUNT);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // More angular distribution
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 2 + Math.random() * 3.5;

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      // Sharper, more aggressive velocities
      velocities[i * 3] = (Math.random() - 0.5) * 0.04;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.04;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.04;

      sizes[i] = Math.random() * 1.5 + 0.3;
      phases[i] = Math.random() * Math.PI * 2;
    }

    return { positions, velocities, sizes, phases };
  }, []);

  // Shader material for particles
  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(stateColors.idle.hex) },
        uSecondaryColor: { value: new THREE.Color(stateColors.idle.secondary) },
        uAudioLevel: { value: 0 },
        uState: { value: 0 },
      },
      vertexShader: `
        attribute float aSize;
        attribute float aPhase;

        uniform float uTime;
        uniform float uAudioLevel;
        uniform float uState;

        varying float vAlpha;
        varying float vDistance;

        void main() {
          vec3 pos = position;

          // Base movement - sharper orbital motion
          float angle = uTime * 0.15 + aPhase;
          float radius = length(pos.xy);

          // State-based effects - more aggressive
          if (uState > 0.5 && uState < 1.5) {
            // Listening - particles expand and pulse sharply
            float pulse = sin(uTime * 6.0 + aPhase) * 0.4;
            pos *= 1.0 + pulse * uAudioLevel;
          } else if (uState > 1.5 && uState < 2.5) {
            // Thinking - aggressive swirling motion
            float swirl = uTime * 0.8 + aPhase;
            pos.x += sin(swirl) * 0.5;
            pos.y += cos(swirl) * 0.5;
            pos.z += sin(swirl * 0.7) * 0.3;
          } else if (uState > 2.5) {
            // Speaking - intense wave-like motion
            float wave = sin(pos.y * 3.0 + uTime * 5.0) * uAudioLevel * 0.7;
            pos.x += wave;
            pos.z += cos(pos.y * 3.0 + uTime * 5.0) * uAudioLevel * 0.5;
          }

          // Sharp breathing effect
          float breathe = sin(uTime * 0.8 + aPhase * 0.1) * 0.12 + 1.0;
          pos *= breathe;

          vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);

          // Distance-based alpha
          vDistance = length(pos);
          vAlpha = smoothstep(6.5, 2.0, vDistance) * (0.4 + uAudioLevel * 0.6);

          // Size based on distance and audio
          float size = aSize * (1.0 + uAudioLevel * 2.5);
          gl_PointSize = size * (350.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform vec3 uSecondaryColor;
        uniform float uTime;

        varying float vAlpha;
        varying float vDistance;

        void main() {
          // Diamond/angular point shape
          vec2 center = gl_PointCoord - 0.5;
          float diamond = abs(center.x) + abs(center.y);
          if (diamond > 0.5) discard;

          // Sharp gradient from center
          float gradient = 1.0 - diamond * 2.0;

          // Mix colors based on distance from center
          vec3 color = mix(uSecondaryColor, uColor, vDistance / 5.0);

          // Sharp pulsing glow
          float pulse = sin(uTime * 3.0) * 0.15 + 0.85;
          color *= pulse;

          gl_FragColor = vec4(color, vAlpha * gradient);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
  }, []);

  // Animation loop
  useFrame((_, delta) => {
    if (!pointsRef.current || !materialRef.current) return;

    const geometry = pointsRef.current.geometry;
    const positionAttr = geometry.attributes.position;
    const posArray = positionAttr.array as Float32Array;

    // Update particle positions with sharper movement
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;

      // Apply velocities
      posArray[i3] += velocities[i3] * delta * 80;
      posArray[i3 + 1] += velocities[i3 + 1] * delta * 80;
      posArray[i3 + 2] += velocities[i3 + 2] * delta * 80;

      // Keep particles in bounds (sphere)
      const dist = Math.sqrt(
        posArray[i3] ** 2 + posArray[i3 + 1] ** 2 + posArray[i3 + 2] ** 2
      );

      if (dist > 5.5 || dist < 1.5) {
        // Sharper bounce
        velocities[i3] *= -0.9 + Math.random() * 0.15;
        velocities[i3 + 1] *= -0.9 + Math.random() * 0.15;
        velocities[i3 + 2] *= -0.9 + Math.random() * 0.15;
      }

      // Stronger gravitational pull to center
      const pull = 0.00015;
      velocities[i3] -= posArray[i3] * pull;
      velocities[i3 + 1] -= posArray[i3 + 1] * pull;
      velocities[i3 + 2] -= posArray[i3 + 2] * pull;
    }

    positionAttr.needsUpdate = true;

    // Update uniforms
    const stateNum = state === 'idle' ? 0 : state === 'listening' ? 1 : state === 'thinking' ? 2 : 3;
    materialRef.current.uniforms.uTime.value += delta;
    materialRef.current.uniforms.uAudioLevel.value += (audioLevel - materialRef.current.uniforms.uAudioLevel.value) * 0.15;
    materialRef.current.uniforms.uState.value += (stateNum - materialRef.current.uniforms.uState.value) * 0.08;

    // Smooth color transition
    const targetColor = new THREE.Color(stateColors[state].hex);
    const targetSecondary = new THREE.Color(stateColors[state].secondary);
    materialRef.current.uniforms.uColor.value.lerp(targetColor, 0.08);
    materialRef.current.uniforms.uSecondaryColor.value.lerp(targetSecondary, 0.08);

    // Rotate entire system - faster than Jarvis
    pointsRef.current.rotation.y += delta * 0.08;
    if (state === 'thinking') {
      pointsRef.current.rotation.x += delta * 0.05;
      pointsRef.current.rotation.z += delta * 0.02;
    }
  });

  // Create geometry
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
    return geo;
  }, [positions, sizes, phases]);

  return (
    <points ref={pointsRef} geometry={geometry}>
      <primitive object={shaderMaterial} ref={materialRef} attach="material" />
    </points>
  );
}

// Core orb in the center - more angular/geometric
function CentralOrb({ state, audioLevel }: ParticleSystemProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (!meshRef.current) return;

    // Sharp breathing effect
    const breathe = Math.sin(Date.now() * 0.0015) * 0.12 + 1;
    const audioScale = 1 + audioLevel * 0.4;
    meshRef.current.scale.setScalar(breathe * audioScale);

    // More aggressive rotation
    meshRef.current.rotation.y += delta * 0.3;
    meshRef.current.rotation.x += delta * 0.1;
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[0.6, 2]} />
      <meshBasicMaterial
        color={stateColors[state].hex}
        transparent
        opacity={0.35 + audioLevel * 0.25}
        wireframe
      />
    </mesh>
  );
}

// Hexagonal rings around the orb
function HexRings({ state, audioLevel }: ParticleSystemProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.z += delta * 0.3;
    if (state === 'speaking') {
      groupRef.current.rotation.x += delta * 0.2;
    }
  });

  if (state === 'idle') return null;

  return (
    <group ref={groupRef}>
      {[1.2, 1.5, 1.8].map((radius, i) => (
        <mesh key={i} rotation={[Math.PI / 2 + i * 0.3, 0, 0]}>
          <torusGeometry args={[radius, 0.02, 6, 6]} />
          <meshBasicMaterial
            color={stateColors[state].hex}
            transparent
            opacity={0.4 - i * 0.1 + audioLevel * 0.3}
          />
        </mesh>
      ))}
    </group>
  );
}

// Camera auto-adjustment
function CameraController() {
  const { camera } = useThree();

  useFrame(() => {
    // More dramatic camera movement
    const time = Date.now() * 0.00012;
    camera.position.x = Math.sin(time) * 0.4;
    camera.position.y = Math.cos(time * 0.7) * 0.3;
    camera.lookAt(0, 0, 0);
  });

  return null;
}

interface UltronFullScreenProps {
  className?: string;
}

export function UltronFullScreen({ className }: UltronFullScreenProps) {
  const [voiceMode, setVoiceMode] = useState<'push-to-talk' | 'voice-activated'>('push-to-talk');
  const [showTaskPanel, setShowTaskPanel] = useState(false);

  const {
    state,
    transcript,
    interimTranscript,
    audioLevel,
    startListening,
    stopListening,
    stopSpeaking,
    speakWithAI,
    isSupported,
    isElevenLabsEnabled,
    // Ultron-specific
    isAutonomousMode,
    autonomyLevel,
    startAutonomousMode,
    stopAutonomousMode,
    setAutonomyLevel,
    backgroundTasks,
    suggestions,
    recentActions,
    dismissSuggestion,
    approveSuggestion,
    removeBackgroundTask,
  } = useUltron();

  const [lastResponse, setLastResponse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isHolding, setIsHolding] = useState(false);

  // Keyboard handling for voice control
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();

        if (state === 'speaking') {
          stopSpeaking();
          return;
        }

        if (voiceMode === 'push-to-talk' && !isHolding && state === 'idle' && !isMuted) {
          setIsHolding(true);
          startListening();
        }

        if (voiceMode === 'voice-activated' && state === 'idle' && !isMuted) {
          startListening();
        }
      }

      if (e.code === 'Escape') {
        e.preventDefault();
        if (state === 'speaking') {
          stopSpeaking();
        } else if (state === 'listening') {
          stopListening();
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        if (voiceMode === 'push-to-talk' && isHolding) {
          setIsHolding(false);
          stopListening();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [isHolding, state, isMuted, voiceMode, startListening, stopListening, stopSpeaking]);

  // Process transcript when listening stops
  useEffect(() => {
    if (state === 'thinking' && transcript) {
      const processMessage = async () => {
        try {
          const response = await speakWithAI(transcript);
          setLastResponse(response);
          setError(null);
        } catch (err) {
          console.error('Voice chat error:', err);
          setError(err instanceof Error ? err.message : 'Failed to process');
        }
      };

      processMessage();
    }
  }, [state, transcript, speakWithAI]);

  // Mic button handlers
  const handleMicDown = useCallback(() => {
    if (state === 'speaking') {
      stopSpeaking();
      return;
    }

    if (!isMuted && isSupported) {
      if (voiceMode === 'push-to-talk' && state === 'idle') {
        setIsHolding(true);
        startListening();
      } else if (voiceMode === 'voice-activated' && state === 'idle') {
        startListening();
      }
    }
  }, [state, isMuted, isSupported, voiceMode, startListening, stopSpeaking]);

  const handleMicUp = useCallback(() => {
    if (voiceMode === 'push-to-talk' && isHolding) {
      setIsHolding(false);
      stopListening();
    }
  }, [isHolding, voiceMode, stopListening]);

  const handleMuteToggle = useCallback(() => {
    setIsMuted(prev => !prev);
    if (!isMuted && state === 'listening') {
      stopListening();
    }
  }, [isMuted, state, stopListening]);

  const handleToggleAutonomousMode = useCallback(() => {
    if (isAutonomousMode) {
      stopAutonomousMode();
    } else {
      startAutonomousMode();
    }
  }, [isAutonomousMode, startAutonomousMode, stopAutonomousMode]);

  const runningTaskCount = backgroundTasks.filter(t => t.status === 'running').length;

  return (
    <div className={cn('fixed inset-0 bg-black', className)}>
      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [0, 0, 8], fov: 60 }}
        className="absolute inset-0"
        gl={{ alpha: true, antialias: true }}
      >
        <CameraController />
        <ambientLight intensity={0.15} />
        <ParticleSystem state={state} audioLevel={audioLevel} />
        <CentralOrb state={state} audioLevel={audioLevel} />
        <HexRings state={state} audioLevel={audioLevel} />
      </Canvas>

      {/* Gradient overlays - darker, more ominous */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute inset-0 transition-opacity duration-1000"
          style={{
            background: `radial-gradient(circle at center, ${stateColors[state].primary}15 0%, transparent 50%)`,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-black/90 to-transparent" />
        <div className="absolute top-0 left-0 right-0 h-40 bg-gradient-to-b from-black/70 to-transparent" />
      </div>

      {/* Header controls */}
      <div className="absolute top-6 left-6 right-6 flex justify-between items-center z-10">
        <Link
          href="/"
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl hover:bg-white/10 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Dashboard</span>
        </Link>

        <div className="flex items-center gap-4">
          {/* Autonomy indicator */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl">
            <div className={cn(
              'w-2 h-2 rounded-full',
              isAutonomousMode ? 'bg-red-500 animate-pulse' : 'bg-gray-500'
            )} />
            <span className="text-xs text-white/60">
              Autonomy: {autonomyLevel}%
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowTaskPanel(!showTaskPanel)}
              className={cn(
                'p-3 rounded-xl backdrop-blur-xl transition-colors relative',
                showTaskPanel
                  ? 'bg-red-500/20 border border-red-500/30 text-red-400'
                  : 'bg-white/5 border border-white/10 hover:bg-white/10'
              )}
            >
              <Activity className="w-5 h-5" />
              {runningTaskCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center">
                  {runningTaskCount}
                </span>
              )}
            </button>

            <button
              onClick={handleMuteToggle}
              className={cn(
                'p-3 rounded-xl backdrop-blur-xl transition-colors',
                isMuted
                  ? 'bg-red-500/20 border border-red-500/30 text-red-400'
                  : 'bg-white/5 border border-white/10 hover:bg-white/10'
              )}
            >
              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </button>

            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-3 rounded-xl bg-white/5 border border-white/10 backdrop-blur-xl hover:bg-white/10 transition-colors"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="absolute top-20 right-6 w-72 p-4 rounded-2xl bg-black/90 border border-red-500/20 backdrop-blur-xl z-20">
          <h3 className="text-sm font-medium mb-4 text-red-400">Ultron Settings</h3>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-white/70">Voice Engine</span>
              {isElevenLabsEnabled ? (
                <span className="text-xs text-emerald-400">ElevenLabs</span>
              ) : (
                <span className="text-xs text-yellow-400">Web Speech</span>
              )}
            </div>

            <div className="pt-2 border-t border-white/10">
              <span className="text-sm text-white/70 block mb-2">Input Mode</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setVoiceMode('push-to-talk')}
                  className={cn(
                    'flex-1 px-3 py-2 rounded-lg text-xs transition-colors',
                    voiceMode === 'push-to-talk'
                      ? 'bg-red-500/30 border border-red-400/50 text-red-300'
                      : 'bg-white/5 border border-white/10 text-white/60 hover:bg-white/10'
                  )}
                >
                  Push to Talk
                </button>
                <button
                  onClick={() => setVoiceMode('voice-activated')}
                  className={cn(
                    'flex-1 px-3 py-2 rounded-lg text-xs transition-colors',
                    voiceMode === 'voice-activated'
                      ? 'bg-red-500/30 border border-red-400/50 text-red-300'
                      : 'bg-white/5 border border-white/10 text-white/60 hover:bg-white/10'
                  )}
                >
                  Voice Activated
                </button>
              </div>
            </div>

            <div className="text-xs text-white/40 pt-2 border-t border-white/10">
              {voiceMode === 'push-to-talk'
                ? 'Hold Space or mic button to speak'
                : 'Press Space to start, speak naturally, silence stops listening'}
            </div>

            <div className="text-xs text-white/40">
              Press Escape to interrupt at any time
            </div>
          </div>
        </div>
      )}

      {/* Task Panel */}
      {showTaskPanel && (
        <div className="absolute top-20 right-6 w-80 h-[calc(100vh-160px)] rounded-2xl bg-black/90 border border-red-500/20 backdrop-blur-xl z-20 overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-red-400" />
              <span className="text-sm font-medium">Ultron Operations</span>
            </div>
            <button
              onClick={() => setShowTaskPanel(false)}
              className="p-1 hover:bg-white/10 rounded"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <UltronTaskPanel
            backgroundTasks={backgroundTasks}
            suggestions={suggestions}
            recentActions={recentActions}
            autonomyLevel={autonomyLevel}
            isAutonomousMode={isAutonomousMode}
            onDismissSuggestion={dismissSuggestion}
            onApproveSuggestion={approveSuggestion}
            onRemoveTask={removeBackgroundTask}
            onSetAutonomyLevel={setAutonomyLevel}
            onToggleAutonomousMode={handleToggleAutonomousMode}
            className="h-[calc(100%-57px)]"
          />
        </div>
      )}

      {/* Main content area */}
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center pb-12 z-10">
        {/* Error display */}
        {error && (
          <div className="mb-6 px-6 py-3 rounded-2xl bg-red-500/10 border border-red-500/20 backdrop-blur-xl">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Transcript display */}
        {(transcript || interimTranscript) && (
          <div className="mb-6 max-w-2xl px-6 py-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
            <p className="text-center text-lg">
              {transcript || <span className="text-white/50">{interimTranscript}</span>}
            </p>
          </div>
        )}

        {/* Last response */}
        {lastResponse && state === 'idle' && !transcript && (
          <div className="mb-6 max-w-2xl px-6 py-4 rounded-2xl bg-red-500/10 border border-red-500/20 backdrop-blur-xl">
            <p className="text-center text-lg text-red-100">{lastResponse}</p>
          </div>
        )}

        {/* Status indicator */}
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-2">
            <Cpu className={cn(
              'w-5 h-5',
              state === 'idle' && 'text-red-500',
              state === 'listening' && 'text-amber-400',
              state === 'thinking' && 'text-violet-400 animate-pulse',
              state === 'speaking' && 'text-rose-400'
            )} />
            <p
              className={cn(
                'text-xl font-light transition-colors duration-500',
                state === 'idle' && 'text-red-400',
                state === 'listening' && 'text-amber-400',
                state === 'thinking' && 'text-violet-400',
                state === 'speaking' && 'text-rose-400'
              )}
            >
              {isMuted ? 'Systems Muted' : stateMessages[voiceMode][state]}
            </p>
          </div>
          <p className="mt-2 text-sm text-white/40">
            Ultron systems operational. State your directive.
          </p>
        </div>

        {/* Mic button */}
        <button
          onMouseDown={handleMicDown}
          onMouseUp={handleMicUp}
          onMouseLeave={handleMicUp}
          onTouchStart={handleMicDown}
          onTouchEnd={handleMicUp}
          disabled={!isSupported || state === 'thinking' || isMuted}
          className={cn(
            'relative w-20 h-20 rounded-full transition-all duration-300',
            'flex items-center justify-center',
            'border-2 select-none',
            state === 'idle' && !isMuted && 'bg-red-500/20 border-red-400/50 hover:bg-red-500/30 cursor-pointer',
            state === 'idle' && isMuted && 'bg-gray-500/10 border-gray-400/30 cursor-not-allowed',
            (state === 'listening' || isHolding) && 'bg-amber-500/30 border-amber-400 scale-110',
            state === 'thinking' && 'bg-violet-600/20 border-violet-500/50 animate-pulse cursor-not-allowed',
            state === 'speaking' && 'bg-rose-500/20 border-rose-400/50 hover:bg-red-500/20 hover:border-red-400/50 cursor-pointer'
          )}
        >
          {/* Ripple effect when listening */}
          {(state === 'listening' || isHolding) && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-amber-400 animate-ping opacity-30" />
              <div className="absolute inset-0 rounded-full border border-amber-400 animate-pulse" />
            </>
          )}

          {!isSupported ? (
            <MicOff className="w-8 h-8 text-red-400" />
          ) : isMuted ? (
            <MicOff className="w-8 h-8 text-gray-400" />
          ) : (
            <Mic
              className={cn(
                'w-8 h-8 transition-colors',
                (state === 'listening' || isHolding) && 'text-amber-300 animate-pulse'
              )}
            />
          )}
        </button>

        {/* Audio level indicator */}
        {state === 'listening' && (
          <div className="mt-6 w-48 h-1 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-500 to-red-400 transition-all duration-75"
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        )}

        {/* Keyboard hint */}
        <p className="mt-6 text-xs text-white/30">
          {voiceMode === 'push-to-talk' ? (
            <>
              Hold{' '}
              <kbd className="px-2 py-1 text-[10px] bg-white/10 rounded border border-white/10">
                Space
              </kbd>
              {' '}or the mic button to speak
            </>
          ) : (
            <>
              Press{' '}
              <kbd className="px-2 py-1 text-[10px] bg-white/10 rounded border border-white/10">
                Space
              </kbd>
              {' '}to start speaking naturally
            </>
          )}
          {' '}&bull;{' '}
          <kbd className="px-2 py-1 text-[10px] bg-white/10 rounded border border-white/10">
            Esc
          </kbd>
          {' '}to stop
        </p>
      </div>
    </div>
  );
}
