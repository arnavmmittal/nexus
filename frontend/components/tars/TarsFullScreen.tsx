'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
import { useVoice, type VoiceState } from '../jarvis/useVoice';
import { cn } from '@/lib/utils';
import { Mic, MicOff, Settings, ArrowLeft, Volume2, VolumeX } from 'lucide-react';
import Link from 'next/link';

// TARS color scheme
const stateColors: Record<VoiceState, { primary: string; led: string; hex: number; ledHex: number }> = {
  idle: { primary: '#4a5568', led: '#fbbf24', hex: 0x4a5568, ledHex: 0xfbbf24 },
  listening: { primary: '#4a5568', led: '#22d3ee', hex: 0x4a5568, ledHex: 0x22d3ee },
  thinking: { primary: '#4a5568', led: '#a78bfa', hex: 0x4a5568, ledHex: 0xa78bfa },
  speaking: { primary: '#4a5568', led: '#fbbf24', hex: 0x4a5568, ledHex: 0xfbbf24 },
};

const stateMessages: Record<VoiceState, string> = {
  idle: 'Hold to speak, Cooper',
  listening: 'Listening...',
  thinking: 'Processing... Humor at 75%',
  speaking: 'Speaking...',
};

// Large-scale TARS segment
function TarsSegmentLarge({
  position,
  index,
  state,
  audioLevel
}: {
  position: [number, number, number];
  index: number;
  state: VoiceState;
  audioLevel: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (!meshRef.current) return;

    let targetRotZ = 0;
    let targetRotY = 0;

    if (state === 'listening') {
      targetRotZ = Math.sin(Date.now() * 0.002 + index * 0.5) * 0.03;
    } else if (state === 'thinking') {
      targetRotY = Math.sin(Date.now() * 0.003 + index) * 0.1;
      targetRotZ = Math.cos(Date.now() * 0.002 + index * 0.3) * 0.05;
    } else if (state === 'speaking') {
      targetRotZ = Math.sin(Date.now() * 0.008 + index) * audioLevel * 0.1;
    }

    meshRef.current.rotation.z += (targetRotZ - meshRef.current.rotation.z) * 0.1;
    meshRef.current.rotation.y += (targetRotY - meshRef.current.rotation.y) * 0.1;
  });

  return (
    <mesh ref={meshRef} position={position}>
      <RoundedBox args={[0.9, 4, 0.3]} radius={0.05} smoothness={4}>
        <meshStandardMaterial
          color={stateColors[state].hex}
          metalness={0.85}
          roughness={0.25}
        />
      </RoundedBox>
      {/* Segment edge lines */}
      <lineSegments position={[0, 0, 0.16]}>
        <edgesGeometry args={[new THREE.BoxGeometry(0.88, 3.98, 0.01)]} />
        <lineBasicMaterial color="#718096" />
      </lineSegments>
    </mesh>
  );
}

// TARS LED display
function TarsLED({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame(() => {
    if (!materialRef.current) return;

    let opacity = 0.6;
    if (state === 'listening') {
      opacity = 0.7 + Math.sin(Date.now() * 0.006) * 0.3;
    } else if (state === 'thinking') {
      // Scanning effect
      opacity = 0.4 + Math.abs(Math.sin(Date.now() * 0.01)) * 0.6;
    } else if (state === 'speaking') {
      opacity = 0.6 + audioLevel * 0.4;
    }

    materialRef.current.opacity = opacity;
    materialRef.current.color.set(stateColors[state].ledHex);
  });

  return (
    <>
      <mesh position={[0, 1.2, 0.17]}>
        <planeGeometry args={[3.4, 0.15]} />
        <meshBasicMaterial
          ref={materialRef}
          color={stateColors[state].ledHex}
          transparent
          opacity={0.6}
        />
      </mesh>
      {/* LED glow */}
      <pointLight
        position={[0, 1.2, 1]}
        intensity={state === 'speaking' ? 1 + audioLevel : 0.5}
        distance={5}
        color={stateColors[state].led}
      />
    </>
  );
}

// Full TARS body
function TarsBodyFull({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (!groupRef.current) return;

    if (state === 'thinking') {
      groupRef.current.rotation.y += delta * 0.15;
    } else {
      groupRef.current.rotation.y *= 0.98;
    }
  });

  const segments = useMemo(() => {
    const segs = [];
    const gap = 0.05;
    const width = 0.9;
    const total = width * 4 + gap * 3;
    const start = -total / 2 + width / 2;

    for (let i = 0; i < 4; i++) {
      segs.push({
        position: [start + i * (width + gap), 0, 0] as [number, number, number],
        index: i,
      });
    }
    return segs;
  }, []);

  return (
    <group ref={groupRef}>
      {segments.map((seg, i) => (
        <TarsSegmentLarge
          key={i}
          position={seg.position}
          index={seg.index}
          state={state}
          audioLevel={audioLevel}
        />
      ))}
      <TarsLED state={state} audioLevel={audioLevel} />
    </group>
  );
}

// Geometric particles
const PARTICLE_COUNT = 1500;

function TarsParticleSystem({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const { positions, velocities } = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const velocities = new Float32Array(PARTICLE_COUNT * 3);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // Rectangular distribution
      const side = Math.floor(Math.random() * 6);
      let x, y, z;

      switch (side) {
        case 0: // Left
          x = -3 - Math.random() * 2;
          y = (Math.random() - 0.5) * 6;
          z = (Math.random() - 0.5) * 2;
          break;
        case 1: // Right
          x = 3 + Math.random() * 2;
          y = (Math.random() - 0.5) * 6;
          z = (Math.random() - 0.5) * 2;
          break;
        case 2: // Top
          x = (Math.random() - 0.5) * 8;
          y = 3 + Math.random() * 2;
          z = (Math.random() - 0.5) * 2;
          break;
        case 3: // Bottom
          x = (Math.random() - 0.5) * 8;
          y = -3 - Math.random() * 2;
          z = (Math.random() - 0.5) * 2;
          break;
        default: // Front/Back
          x = (Math.random() - 0.5) * 6;
          y = (Math.random() - 0.5) * 6;
          z = (Math.random() > 0.5 ? 2 : -2) + (Math.random() - 0.5);
      }

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      velocities[i * 3] = (Math.random() - 0.5) * 0.015;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.015;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.015;
    }

    return { positions, velocities };
  }, []);

  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(stateColors.idle.ledHex) },
        uAudioLevel: { value: 0 },
      },
      vertexShader: `
        uniform float uTime;
        uniform float uAudioLevel;
        varying float vAlpha;

        void main() {
          vec3 pos = position;

          // Subtle movement
          pos.x += sin(uTime + position.y) * 0.1;
          pos.y += cos(uTime * 0.5 + position.x) * 0.1;

          vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);

          float dist = length(position);
          vAlpha = smoothstep(6.0, 2.0, dist) * (0.3 + uAudioLevel * 0.5);

          gl_PointSize = (2.0 + uAudioLevel * 2.0) * (200.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying float vAlpha;

        void main() {
          vec2 center = gl_PointCoord - 0.5;
          float dist = length(center);
          if (dist > 0.5) discard;

          float gradient = 1.0 - dist * 2.0;
          gl_FragColor = vec4(uColor, vAlpha * gradient);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
  }, []);

  useFrame((_, delta) => {
    if (!pointsRef.current || !materialRef.current) return;

    const posAttr = pointsRef.current.geometry.attributes.position;
    const posArray = posAttr.array as Float32Array;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      posArray[i3] += velocities[i3] * delta * 60;
      posArray[i3 + 1] += velocities[i3 + 1] * delta * 60;
      posArray[i3 + 2] += velocities[i3 + 2] * delta * 60;

      if (Math.abs(posArray[i3]) > 5) velocities[i3] *= -1;
      if (Math.abs(posArray[i3 + 1]) > 5) velocities[i3 + 1] *= -1;
      if (Math.abs(posArray[i3 + 2]) > 3) velocities[i3 + 2] *= -1;
    }

    posAttr.needsUpdate = true;

    materialRef.current.uniforms.uTime.value += delta;
    materialRef.current.uniforms.uAudioLevel.value += (audioLevel - materialRef.current.uniforms.uAudioLevel.value) * 0.1;
    materialRef.current.uniforms.uColor.value.set(stateColors[state].ledHex);
  });

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, [positions]);

  return (
    <points ref={pointsRef} geometry={geometry}>
      <primitive object={shaderMaterial} ref={materialRef} attach="material" />
    </points>
  );
}

function CameraController() {
  const { camera } = useThree();

  useFrame(() => {
    const time = Date.now() * 0.0001;
    camera.position.x = Math.sin(time) * 0.5;
    camera.position.y = Math.cos(time * 0.7) * 0.3;
    camera.lookAt(0, 0, 0);
  });

  return null;
}

export function TarsFullScreen({ className }: { className?: string }) {
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

  const [lastResponse, setLastResponse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isHolding, setIsHolding] = useState(false);

  // Keyboard handling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        if (!isHolding && state === 'idle' && !isMuted) {
          setIsHolding(true);
          startListening();
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        if (isHolding) {
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
  }, [isHolding, state, isMuted, startListening, stopListening]);

  // Process transcript
  useEffect(() => {
    if (state === 'thinking' && transcript) {
      const processMessage = async () => {
        try {
          // TARS personality
          const tarsPrompt = `[You are TARS from Interstellar. Be helpful but with dry wit. Humor setting: 75%. Keep responses concise.] ${transcript}`;
          const response = await speakWithAI(tarsPrompt);
          setLastResponse(response);
          setError(null);
        } catch (err) {
          console.error('TARS error:', err);
          setError(err instanceof Error ? err.message : 'Processing failed');
        }
      };
      processMessage();
    }
  }, [state, transcript, speakWithAI]);

  const handleMicDown = useCallback(() => {
    if (state === 'idle' && !isMuted && isSupported) {
      setIsHolding(true);
      startListening();
    }
  }, [state, isMuted, isSupported, startListening]);

  const handleMicUp = useCallback(() => {
    if (isHolding) {
      setIsHolding(false);
      stopListening();
    }
  }, [isHolding, stopListening]);

  return (
    <div className={cn('fixed inset-0 bg-black', className)}>
      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [0, 0, 10], fov: 50 }}
        className="absolute inset-0"
        gl={{ alpha: true, antialias: true }}
      >
        <CameraController />
        <ambientLight intensity={0.3} />
        <directionalLight position={[5, 5, 5]} intensity={0.5} />
        <TarsBodyFull state={state} audioLevel={audioLevel} />
        <TarsParticleSystem state={state} audioLevel={audioLevel} />
      </Canvas>

      {/* Overlays */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute inset-0 transition-opacity duration-1000"
          style={{
            background: `radial-gradient(circle at center, ${stateColors[state].led}08 0%, transparent 50%)`,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 h-64 bg-gradient-to-t from-black/80 to-transparent" />
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black/60 to-transparent" />
      </div>

      {/* Header */}
      <div className="absolute top-6 left-6 right-6 flex justify-between items-center z-10">
        <Link
          href="/"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-amber-500/20 backdrop-blur-xl hover:bg-white/10 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-mono">Dashboard</span>
        </Link>

        <div className="flex items-center gap-4">
          <span className="text-xs font-mono text-amber-400">TARS // Humor: 75%</span>
          <button
            onClick={() => setIsMuted(!isMuted)}
            className={cn(
              'p-3 rounded-lg backdrop-blur-xl transition-colors',
              isMuted
                ? 'bg-red-500/20 border border-red-500/30 text-red-400'
                : 'bg-white/5 border border-amber-500/20 hover:bg-white/10'
            )}
          >
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center pb-12 z-10">
        {error && (
          <div className="mb-6 px-6 py-3 rounded-lg bg-red-500/10 border border-red-500/20 backdrop-blur-xl">
            <p className="text-sm text-red-400 font-mono">{error}</p>
          </div>
        )}

        {(transcript || interimTranscript) && (
          <div className="mb-6 max-w-2xl px-6 py-4 rounded-lg bg-white/5 border border-amber-500/20 backdrop-blur-xl">
            <p className="text-center text-lg font-mono">
              {transcript || <span className="text-white/50">{interimTranscript}</span>}
            </p>
          </div>
        )}

        {lastResponse && state === 'idle' && !transcript && (
          <div className="mb-6 max-w-2xl px-6 py-4 rounded-lg bg-amber-500/10 border border-amber-500/20 backdrop-blur-xl">
            <p className="text-center text-lg text-amber-100 font-mono">{lastResponse}</p>
          </div>
        )}

        <div className="mb-8 text-center">
          <p
            className={cn(
              'text-xl font-mono transition-colors duration-500',
              state === 'idle' && 'text-amber-400',
              state === 'listening' && 'text-cyan-400',
              state === 'thinking' && 'text-purple-400',
              state === 'speaking' && 'text-amber-400'
            )}
          >
            {isMuted ? 'Muted' : stateMessages[state]}
          </p>
        </div>

        {/* Mic button */}
        <button
          onMouseDown={handleMicDown}
          onMouseUp={handleMicUp}
          onMouseLeave={handleMicUp}
          onTouchStart={handleMicDown}
          onTouchEnd={handleMicUp}
          disabled={!isSupported || state === 'thinking' || state === 'speaking' || isMuted}
          className={cn(
            'relative w-20 h-20 rounded-lg transition-all duration-300',
            'flex items-center justify-center',
            'border-2 select-none',
            state === 'idle' && !isMuted && 'bg-amber-500/20 border-amber-400/50 hover:bg-amber-500/30 cursor-pointer',
            state === 'idle' && isMuted && 'bg-red-500/10 border-red-400/30 cursor-not-allowed',
            (state === 'listening' || isHolding) && 'bg-cyan-500/30 border-cyan-400 scale-110',
            state === 'thinking' && 'bg-purple-500/20 border-purple-400/50 animate-pulse',
            state === 'speaking' && 'bg-amber-500/20 border-amber-400/50'
          )}
        >
          {(state === 'listening' || isHolding) && (
            <div className="absolute inset-0 rounded-lg border-2 border-cyan-400 animate-ping opacity-30" />
          )}

          {!isSupported || isMuted ? (
            <MicOff className="w-8 h-8 text-red-400" />
          ) : (
            <Mic
              className={cn(
                'w-8 h-8 transition-colors',
                (state === 'listening' || isHolding) && 'text-cyan-300 animate-pulse'
              )}
            />
          )}
        </button>

        {state === 'listening' && (
          <div className="mt-6 w-48 h-1 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-400 to-cyan-400 transition-all duration-75"
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        )}

        <p className="mt-6 text-xs text-white/30 font-mono">
          Hold{' '}
          <kbd className="px-2 py-1 text-[10px] bg-white/10 rounded border border-white/10">
            Space
          </kbd>
          {' '}to speak
        </p>
      </div>
    </div>
  );
}
