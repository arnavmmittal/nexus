'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { RoundedBox, Float } from '@react-three/drei';
import * as THREE from 'three';
import type { VoiceState } from '../jarvis/useVoice';

// TARS color scheme - metallic gunmetal/silver
const stateColors: Record<VoiceState, { primary: string; led: string; hex: number }> = {
  idle: { primary: '#4a5568', led: '#fbbf24', hex: 0x4a5568 },      // Gunmetal + amber LED
  listening: { primary: '#4a5568', led: '#22d3ee', hex: 0x4a5568 }, // Gunmetal + cyan LED
  thinking: { primary: '#4a5568', led: '#a78bfa', hex: 0x4a5568 },  // Gunmetal + purple LED
  speaking: { primary: '#4a5568', led: '#fbbf24', hex: 0x4a5568 },  // Gunmetal + amber LED (brighter)
};

interface TarsSegmentProps {
  position: [number, number, number];
  rotation: number;
  index: number;
  state: VoiceState;
  audioLevel: number;
}

// Individual TARS segment (the robot has 4 main articulating segments)
function TarsSegment({ position, rotation, index, state, audioLevel }: TarsSegmentProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const targetRotation = useRef(0);

  useFrame((_, delta) => {
    if (!meshRef.current) return;

    // Different animation per state
    let targetRot = 0;

    if (state === 'listening') {
      // Slight tilt when listening
      targetRot = Math.sin(Date.now() * 0.002 + index) * 0.05;
    } else if (state === 'thinking') {
      // Rotation when thinking (like TARS processing)
      targetRot = Math.sin(Date.now() * 0.003 + index * 0.5) * 0.1;
    } else if (state === 'speaking') {
      // Articulation when speaking
      targetRot = Math.sin(Date.now() * 0.005 + index) * audioLevel * 0.15;
    }

    targetRotation.current += (targetRot - targetRotation.current) * 0.1;
    meshRef.current.rotation.z = rotation + targetRotation.current;
  });

  return (
    <mesh ref={meshRef} position={position} rotation={[0, 0, rotation]}>
      <RoundedBox args={[0.45, 2.2, 0.15]} radius={0.02} smoothness={4}>
        <meshStandardMaterial
          color={stateColors[state].hex}
          metalness={0.8}
          roughness={0.3}
        />
      </RoundedBox>
    </mesh>
  );
}

// LED communication strip on TARS
function LedStrip({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const stripRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);
  const targetIntensity = useRef(0.5);

  useFrame(() => {
    if (!materialRef.current) return;

    // Pulse the LED based on state
    let intensity = 0.5;

    if (state === 'listening') {
      intensity = 0.7 + Math.sin(Date.now() * 0.005) * 0.3;
    } else if (state === 'thinking') {
      // Scanning effect
      intensity = 0.5 + Math.abs(Math.sin(Date.now() * 0.008)) * 0.5;
    } else if (state === 'speaking') {
      // Audio reactive
      intensity = 0.6 + audioLevel * 0.4;
    }

    targetIntensity.current += (intensity - targetIntensity.current) * 0.15;
    materialRef.current.opacity = targetIntensity.current;
  });

  return (
    <mesh ref={stripRef} position={[0, 0.6, 0.09]}>
      <planeGeometry args={[1.6, 0.08]} />
      <meshBasicMaterial
        ref={materialRef}
        color={stateColors[state].led}
        transparent
        opacity={0.5}
      />
    </mesh>
  );
}

// LED glow effect
function LedGlow({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const glowRef = useRef<THREE.PointLight>(null);

  useFrame(() => {
    if (!glowRef.current) return;

    let intensity = 0.5;
    if (state === 'speaking') {
      intensity = 0.5 + audioLevel * 1.5;
    } else if (state === 'thinking') {
      intensity = 0.3 + Math.abs(Math.sin(Date.now() * 0.008)) * 0.7;
    } else if (state === 'listening') {
      intensity = 0.5 + Math.sin(Date.now() * 0.005) * 0.3;
    }

    glowRef.current.intensity = intensity;
    glowRef.current.color.set(stateColors[state].led);
  });

  return (
    <pointLight
      ref={glowRef}
      position={[0, 0.6, 0.5]}
      intensity={0.5}
      distance={3}
      color={stateColors[state].led}
    />
  );
}

// Main TARS body - the monolith with 4 segments
function TarsBody({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const segmentGap = 0.02;

  useFrame((_, delta) => {
    if (!groupRef.current) return;

    // Subtle rotation based on state
    if (state === 'thinking') {
      groupRef.current.rotation.y += delta * 0.3;
    } else if (state === 'speaking') {
      // Gentle sway when speaking
      groupRef.current.rotation.y = Math.sin(Date.now() * 0.001) * 0.05;
    } else {
      // Return to center
      groupRef.current.rotation.y *= 0.95;
    }
  });

  // 4 segments arranged horizontally (like TARS)
  const segments = useMemo(() => {
    const segs = [];
    const segmentWidth = 0.45;
    const totalWidth = segmentWidth * 4 + segmentGap * 3;
    const startX = -totalWidth / 2 + segmentWidth / 2;

    for (let i = 0; i < 4; i++) {
      segs.push({
        position: [startX + i * (segmentWidth + segmentGap), 0, 0] as [number, number, number],
        rotation: 0,
        index: i,
      });
    }
    return segs;
  }, []);

  return (
    <group ref={groupRef}>
      {/* Main segments */}
      {segments.map((seg, i) => (
        <TarsSegment
          key={i}
          position={seg.position}
          rotation={seg.rotation}
          index={seg.index}
          state={state}
          audioLevel={audioLevel}
        />
      ))}

      {/* LED strip */}
      <LedStrip state={state} audioLevel={audioLevel} />

      {/* LED glow */}
      <LedGlow state={state} audioLevel={audioLevel} />

      {/* Edge highlights */}
      <mesh position={[0, -1.15, 0.08]}>
        <planeGeometry args={[1.9, 0.02]} />
        <meshBasicMaterial color="#718096" />
      </mesh>
      <mesh position={[0, 1.15, 0.08]}>
        <planeGeometry args={[1.9, 0.02]} />
        <meshBasicMaterial color="#718096" />
      </mesh>
    </group>
  );
}

// Geometric particles for TARS (more angular than Jarvis)
function TarsParticles({ state, audioLevel }: { state: VoiceState; audioLevel: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const particleCount = 200;

  const { positions, velocities } = useMemo(() => {
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      // Rectangular distribution around TARS
      const side = Math.floor(Math.random() * 4);
      let x, y, z;

      if (side === 0) { // Left
        x = -1.5 - Math.random() * 0.5;
        y = (Math.random() - 0.5) * 3;
        z = (Math.random() - 0.5) * 0.5;
      } else if (side === 1) { // Right
        x = 1.5 + Math.random() * 0.5;
        y = (Math.random() - 0.5) * 3;
        z = (Math.random() - 0.5) * 0.5;
      } else if (side === 2) { // Top
        x = (Math.random() - 0.5) * 3;
        y = 1.5 + Math.random() * 0.5;
        z = (Math.random() - 0.5) * 0.5;
      } else { // Bottom
        x = (Math.random() - 0.5) * 3;
        y = -1.5 - Math.random() * 0.5;
        z = (Math.random() - 0.5) * 0.5;
      }

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      velocities[i * 3] = (Math.random() - 0.5) * 0.01;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.01;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.01;
    }

    return { positions, velocities };
  }, []);

  useFrame((_, delta) => {
    if (!pointsRef.current) return;

    const positionAttr = pointsRef.current.geometry.attributes.position;
    const posArray = positionAttr.array as Float32Array;

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;

      // Apply velocities
      posArray[i3] += velocities[i3] * delta * 60;
      posArray[i3 + 1] += velocities[i3 + 1] * delta * 60;
      posArray[i3 + 2] += velocities[i3 + 2] * delta * 60;

      // Bounds check
      if (Math.abs(posArray[i3]) > 2.5) velocities[i3] *= -1;
      if (Math.abs(posArray[i3 + 1]) > 2) velocities[i3 + 1] *= -1;
      if (Math.abs(posArray[i3 + 2]) > 1) velocities[i3 + 2] *= -1;
    }

    positionAttr.needsUpdate = true;

    // Rotate based on state
    if (state === 'thinking') {
      pointsRef.current.rotation.y += delta * 0.2;
    }
  });

  if (state === 'idle') return null;

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particleCount}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.03}
        color={stateColors[state].led}
        transparent
        opacity={0.6}
        sizeAttenuation
      />
    </points>
  );
}

interface TarsMonolithProps {
  state: VoiceState;
  audioLevel?: number;
  size?: number;
  className?: string;
}

export function TarsMonolith({ state, audioLevel = 0, size = 160, className = '' }: TarsMonolithProps) {
  return (
    <div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Ambient glow */}
      <div
        className="absolute inset-0 rounded-lg blur-2xl opacity-30 transition-colors duration-500"
        style={{
          background: `radial-gradient(circle, ${stateColors[state].led}30 0%, transparent 70%)`,
        }}
      />

      <Canvas
        camera={{ position: [0, 0, 4], fov: 45 }}
        style={{ background: 'transparent' }}
        gl={{ alpha: true, antialias: true }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={0.6} />
        <directionalLight position={[-5, -5, 5]} intensity={0.3} />

        <Float
          speed={1.5}
          rotationIntensity={0.1}
          floatIntensity={0.2}
        >
          <group scale={0.6}>
            <TarsBody state={state} audioLevel={audioLevel} />
            <TarsParticles state={state} audioLevel={audioLevel} />
          </group>
        </Float>
      </Canvas>
    </div>
  );
}
