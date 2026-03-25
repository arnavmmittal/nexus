'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame, extend } from '@react-three/fiber';
import { shaderMaterial, Float, Stars } from '@react-three/drei';
import * as THREE from 'three';
import type { VoiceState } from './useVoice';

// Custom shader material for the orb
const OrbShaderMaterial = shaderMaterial(
  {
    uTime: 0,
    uState: 0, // 0=idle, 1=listening, 2=thinking, 3=speaking
    uAudioLevel: 0,
    uColor: new THREE.Color('#3b82f6'),
    uGlowColor: new THREE.Color('#3b82f6'),
    uFresnelPower: 2.0,
  },
  // Vertex shader
  /* glsl */ `
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec2 vUv;
    varying float vDisplacement;

    uniform float uTime;
    uniform float uState;
    uniform float uAudioLevel;

    // Noise function for organic distortion
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

    float snoise(vec3 v) {
      const vec2 C = vec2(1.0/6.0, 1.0/3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

      vec3 i  = floor(v + dot(v, C.yyy));
      vec3 x0 = v - i + dot(i, C.xxx);

      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min(g.xyz, l.zxy);
      vec3 i2 = max(g.xyz, l.zxy);

      vec3 x1 = x0 - i1 + C.xxx;
      vec3 x2 = x0 - i2 + C.yyy;
      vec3 x3 = x0 - D.yyy;

      i = mod289(i);
      vec4 p = permute(permute(permute(
        i.z + vec4(0.0, i1.z, i2.z, 1.0))
        + i.y + vec4(0.0, i1.y, i2.y, 1.0))
        + i.x + vec4(0.0, i1.x, i2.x, 1.0));

      float n_ = 0.142857142857;
      vec3 ns = n_ * D.wyz - D.xzx;

      vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_);

      vec4 x = x_ *ns.x + ns.yyyy;
      vec4 y = y_ *ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);

      vec4 b0 = vec4(x.xy, y.xy);
      vec4 b1 = vec4(x.zw, y.zw);

      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));

      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;

      vec3 p0 = vec3(a0.xy, h.x);
      vec3 p1 = vec3(a0.zw, h.y);
      vec3 p2 = vec3(a1.xy, h.z);
      vec3 p3 = vec3(a1.zw, h.w);

      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
      p0 *= norm.x;
      p1 *= norm.y;
      p2 *= norm.z;
      p3 *= norm.w;

      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
    }

    void main() {
      vNormal = normalize(normalMatrix * normal);
      vUv = uv;

      vec3 pos = position;
      float displacement = 0.0;

      // Idle: gentle breathing
      float breathe = sin(uTime * 0.5) * 0.03 + 1.0;

      // Listening: expanded with ripples
      if (uState >= 0.5 && uState < 1.5) {
        float scale = 1.15;
        float ripple = sin(length(pos.xy) * 8.0 - uTime * 4.0) * 0.02 * uAudioLevel;
        displacement = ripple;
        pos *= scale;
      }
      // Thinking: organic morphing
      else if (uState >= 1.5 && uState < 2.5) {
        float noise = snoise(pos * 3.0 + uTime * 0.5) * 0.1;
        displacement = noise;
        pos += normal * noise;
      }
      // Speaking: audio-reactive waveform
      else if (uState >= 2.5) {
        float wave = sin(pos.y * 10.0 + uTime * 5.0) * uAudioLevel * 0.15;
        wave += sin(pos.x * 8.0 + uTime * 3.0) * uAudioLevel * 0.1;
        displacement = wave;
        pos += normal * wave;
      }

      pos *= breathe;
      vDisplacement = displacement;
      vPosition = pos;

      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
  `,
  // Fragment shader
  /* glsl */ `
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec2 vUv;
    varying float vDisplacement;

    uniform float uTime;
    uniform float uState;
    uniform float uAudioLevel;
    uniform vec3 uColor;
    uniform vec3 uGlowColor;
    uniform float uFresnelPower;

    void main() {
      // Calculate fresnel effect for edge glow
      vec3 viewDirection = normalize(cameraPosition - vPosition);
      float fresnel = pow(1.0 - dot(viewDirection, vNormal), uFresnelPower);

      // Base color with gradient
      vec3 baseColor = uColor;

      // Add core glow
      float coreGlow = 1.0 - length(vUv - 0.5) * 1.5;
      coreGlow = max(0.0, coreGlow);

      // Pulsing effect
      float pulse = sin(uTime * 2.0) * 0.1 + 0.9;

      // Combine effects
      vec3 finalColor = baseColor * pulse;
      finalColor += uGlowColor * fresnel * 0.8;
      finalColor += uGlowColor * coreGlow * 0.5;

      // Add displacement-based color variation
      finalColor += abs(vDisplacement) * uGlowColor * 3.0;

      // Audio level brightness boost
      finalColor += uAudioLevel * 0.3 * uGlowColor;

      // Alpha with fresnel-based edge fade
      float alpha = 0.85 + fresnel * 0.15;

      gl_FragColor = vec4(finalColor, alpha);
    }
  `
);

// Extend Three.js with our custom material
extend({ OrbShaderMaterial });

// Color configurations for different states
const stateColors: Record<VoiceState, { color: string; glow: string }> = {
  idle: { color: '#3b82f6', glow: '#60a5fa' }, // Blue
  listening: { color: '#06b6d4', glow: '#22d3ee' }, // Cyan
  thinking: { color: '#8b5cf6', glow: '#a78bfa' }, // Purple
  speaking: { color: '#10b981', glow: '#34d399' }, // Green
};

// State to numeric value
const stateToNumber: Record<VoiceState, number> = {
  idle: 0,
  listening: 1,
  thinking: 2,
  speaking: 3,
};

interface OrbMeshProps {
  state: VoiceState;
  audioLevel: number;
}

// Custom material type
type OrbMaterialType = THREE.ShaderMaterial & {
  uTime: number;
  uState: number;
  uAudioLevel: number;
  uColor: THREE.Color;
  uGlowColor: THREE.Color;
  uFresnelPower: number;
};

function OrbMesh({ state, audioLevel }: OrbMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<OrbMaterialType>(null);

  const colors = useMemo(() => stateColors[state], [state]);
  const targetColor = useMemo(() => new THREE.Color(colors.color), [colors.color]);
  const targetGlow = useMemo(() => new THREE.Color(colors.glow), [colors.glow]);

  // Create the material instance
  const material = useMemo(() => {
    const mat = new OrbShaderMaterial() as OrbMaterialType;
    mat.transparent = true;
    mat.uTime = 0;
    mat.uState = stateToNumber[state];
    mat.uAudioLevel = audioLevel;
    mat.uColor = new THREE.Color(colors.color);
    mat.uGlowColor = new THREE.Color(colors.glow);
    mat.uFresnelPower = 2.5;
    return mat;
  }, []);

  useFrame((_, delta) => {
    if (materialRef.current) {
      // Update time
      materialRef.current.uTime += delta;

      // Smooth state transition
      const targetState = stateToNumber[state];
      materialRef.current.uState += (targetState - materialRef.current.uState) * 0.1;

      // Smooth audio level
      materialRef.current.uAudioLevel += (audioLevel - materialRef.current.uAudioLevel) * 0.15;

      // Smooth color transition
      materialRef.current.uColor.lerp(targetColor, 0.05);
      materialRef.current.uGlowColor.lerp(targetGlow, 0.05);
    }

    // Subtle rotation
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.1;
      if (state === 'thinking') {
        meshRef.current.rotation.x += delta * 0.2;
      }
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 64, 64]} />
      <primitive object={material} ref={materialRef} attach="material" />
    </mesh>
  );
}

// Outer glow rings
function GlowRings({ state, audioLevel }: OrbMeshProps) {
  const ringsRef = useRef<THREE.Group>(null);
  const colors = stateColors[state];

  useFrame((_, delta) => {
    if (ringsRef.current) {
      ringsRef.current.rotation.z += delta * 0.3;
      if (state === 'listening') {
        ringsRef.current.rotation.x += delta * 0.2;
      }
    }
  });

  if (state === 'idle') return null;

  const ringCount = state === 'listening' ? 3 : state === 'thinking' ? 2 : 4;
  const opacity = state === 'speaking' ? 0.3 + audioLevel * 0.4 : 0.2;

  return (
    <group ref={ringsRef}>
      {Array.from({ length: ringCount }).map((_, i) => (
        <mesh key={i} rotation={[Math.PI / 2 + i * 0.3, i * 0.5, 0]}>
          <torusGeometry args={[1.3 + i * 0.15, 0.01 + i * 0.005, 16, 64]} />
          <meshBasicMaterial
            color={colors.glow}
            transparent
            opacity={opacity - i * 0.05}
          />
        </mesh>
      ))}
    </group>
  );
}

// Main particle sphere that forms the orb shape (always visible)
function OrbParticles({ state, audioLevel }: OrbMeshProps) {
  const particlesRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const particleCount = 2000;

  const { positions, originalPositions, sizes, phases } = useMemo(() => {
    const positions = new Float32Array(particleCount * 3);
    const originalPositions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const phases = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      // Fibonacci sphere distribution for even particle spacing
      const y = 1 - (i / (particleCount - 1)) * 2;
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = ((i % particleCount) * 2.399963) + Math.random() * 0.1; // Golden angle

      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      originalPositions[i * 3] = x;
      originalPositions[i * 3 + 1] = y;
      originalPositions[i * 3 + 2] = z;

      sizes[i] = Math.random() * 2 + 1;
      phases[i] = Math.random() * Math.PI * 2;
    }

    return { positions, originalPositions, sizes, phases };
  }, []);

  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(stateColors.idle.color) },
        uSecondaryColor: { value: new THREE.Color(stateColors.idle.glow) },
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
          float phase = aPhase;

          // Breathing effect
          float breathe = sin(uTime * 0.5 + phase * 0.1) * 0.05 + 1.0;
          pos *= breathe;

          // State-based effects
          if (uState >= 0.5 && uState < 1.5) {
            // Listening - expand and pulse
            float pulse = sin(uTime * 4.0 + phase) * 0.1 * uAudioLevel;
            pos *= 1.1 + pulse;
          } else if (uState >= 1.5 && uState < 2.5) {
            // Thinking - swirl
            float swirl = uTime * 0.5 + phase;
            pos.x += sin(swirl + pos.y * 3.0) * 0.1;
            pos.z += cos(swirl + pos.y * 3.0) * 0.1;
          } else if (uState >= 2.5) {
            // Speaking - wave
            float wave = sin(pos.y * 5.0 + uTime * 4.0) * uAudioLevel * 0.15;
            pos.x += wave;
            pos.z += cos(pos.y * 5.0 + uTime * 4.0) * uAudioLevel * 0.1;
          }

          vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);

          vDistance = length(pos);
          vAlpha = 0.6 + uAudioLevel * 0.4;

          float size = aSize * (1.5 + uAudioLevel * 1.0);
          gl_PointSize = size * (250.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform vec3 uSecondaryColor;
        uniform float uTime;
        uniform float uAudioLevel;

        varying float vAlpha;
        varying float vDistance;

        void main() {
          vec2 center = gl_PointCoord - 0.5;
          float dist = length(center);
          if (dist > 0.5) discard;

          // Soft circular gradient
          float gradient = 1.0 - smoothstep(0.0, 0.5, dist);

          // Color based on position
          vec3 color = mix(uColor, uSecondaryColor, vDistance * 0.5);

          // Pulse effect
          float pulse = sin(uTime * 2.0) * 0.1 + 0.9;
          color *= pulse;

          // Glow at center
          color += uSecondaryColor * gradient * 0.3;

          gl_FragColor = vec4(color, vAlpha * gradient);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
  }, []);

  useFrame((_, delta) => {
    if (!particlesRef.current || !materialRef.current) return;

    // Update uniforms
    const stateNum = state === 'idle' ? 0 : state === 'listening' ? 1 : state === 'thinking' ? 2 : 3;
    materialRef.current.uniforms.uTime.value += delta;
    materialRef.current.uniforms.uAudioLevel.value += (audioLevel - materialRef.current.uniforms.uAudioLevel.value) * 0.15;
    materialRef.current.uniforms.uState.value += (stateNum - materialRef.current.uniforms.uState.value) * 0.1;

    // Color transition
    const targetColor = new THREE.Color(stateColors[state].color);
    const targetSecondary = new THREE.Color(stateColors[state].glow);
    materialRef.current.uniforms.uColor.value.lerp(targetColor, 0.05);
    materialRef.current.uniforms.uSecondaryColor.value.lerp(targetSecondary, 0.05);

    // Rotate
    particlesRef.current.rotation.y += delta * 0.1;
    if (state === 'thinking') {
      particlesRef.current.rotation.x += delta * 0.15;
    }
  });

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
    return geo;
  }, [positions, sizes, phases]);

  return (
    <points ref={particlesRef} geometry={geometry}>
      <primitive object={shaderMaterial} ref={materialRef} attach="material" />
    </points>
  );
}

// Outer orbital particles
function OrbitalParticles({ state, audioLevel }: OrbMeshProps) {
  const particlesRef = useRef<THREE.Points>(null);
  const particleCount = 500;

  const { positions, sizes, phases } = useMemo(() => {
    const positions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const phases = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.2 + Math.random() * 0.8;

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      sizes[i] = Math.random() * 1.5 + 0.5;
      phases[i] = Math.random() * Math.PI * 2;
    }

    return { positions, sizes, phases };
  }, []);

  useFrame((_, delta) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y += delta * 0.2;
      if (state === 'thinking') {
        particlesRef.current.rotation.x += delta * 0.3;
        particlesRef.current.rotation.z += delta * 0.1;
      }
    }
  });

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, [positions]);

  return (
    <points ref={particlesRef} geometry={geometry}>
      <pointsMaterial
        size={0.02}
        color={stateColors[state].glow}
        transparent
        opacity={state === 'idle' ? 0.3 : 0.6 + audioLevel * 0.4}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

interface JarvisOrbProps {
  state: VoiceState;
  audioLevel?: number;
  size?: number;
  className?: string;
}

export function JarvisOrb({ state, audioLevel = 0, size = 160, className = '' }: JarvisOrbProps) {
  return (
    <div
      className={`relative ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Ambient glow background */}
      <div
        className="absolute inset-0 rounded-full blur-3xl opacity-40 transition-colors duration-500"
        style={{
          background: `radial-gradient(circle, ${stateColors[state].glow}40 0%, transparent 70%)`,
        }}
      />

      {/* Secondary glow layer */}
      <div
        className="absolute inset-4 rounded-full blur-xl opacity-60 transition-colors duration-500"
        style={{
          background: `radial-gradient(circle, ${stateColors[state].color}50 0%, transparent 60%)`,
        }}
      />

      {/* Three.js Canvas */}
      <Canvas
        camera={{ position: [0, 0, 3.5], fov: 45 }}
        style={{ background: 'transparent' }}
        gl={{ alpha: true, antialias: true }}
      >
        {/* Ambient lighting */}
        <ambientLight intensity={0.4} />
        <pointLight position={[5, 5, 5]} intensity={0.6} color="#ffffff" />
        <pointLight position={[-5, -5, 5]} intensity={0.3} color={stateColors[state].glow} />

        {/* Floating animation wrapper */}
        <Float
          speed={2}
          rotationIntensity={0.2}
          floatIntensity={0.3}
        >
          <group>
            {/* Main particle orb - dotted appearance */}
            <OrbParticles state={state} audioLevel={audioLevel} />

            {/* Orbital particles */}
            <OrbitalParticles state={state} audioLevel={audioLevel} />

            {/* Glow rings */}
            <GlowRings state={state} audioLevel={audioLevel} />
          </group>
        </Float>

        {/* Background stars for atmosphere */}
        <Stars
          radius={50}
          depth={50}
          count={1000}
          factor={2}
          saturation={0}
          fade
          speed={0.5}
        />
      </Canvas>
    </div>
  );
}
