# Nexus JARVIS Voice Interface

## Overview

A visual and voice interface inspired by Iron Man's JARVIS - featuring an animated orb/sphere visualization that responds to voice input and speaks back using ElevenLabs.

---

## Visual Design: The Nexus Orb

### Concept
A glowing, pulsing orb that serves as the visual representation of Nexus AI. The orb:
- Pulses gently when idle (ambient breathing effect)
- Expands and ripples when listening
- Animates with audio waveform when speaking
- Changes color based on context/mood

### Visual States

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│           IDLE                    LISTENING                 │
│                                                             │
│         ╭─────╮                    ╭───────╮               │
│        ╱ ░░░░░ ╲                  ╱ ▓▓▓▓▓▓▓ ╲              │
│       │ ░░░░░░░ │   ──────►     │ ▓▓▓▓▓▓▓▓▓ │             │
│        ╲ ░░░░░ ╱                  ╲ ▓▓▓▓▓▓▓ ╱              │
│         ╰─────╯                    ╰───────╯               │
│      Gentle pulse               Expanded, rippling          │
│      Soft blue glow             Bright cyan glow            │
│                                                             │
│                                                             │
│          SPEAKING                   THINKING                │
│                                                             │
│         ╭─────╮                    ╭─────╮                 │
│        ╱ █▓░▓█ ╲                  ╱ ◠◡◠◡◠ ╲               │
│       │ ░▓███▓░ │                │ ◡◠◡◠◡◠◡ │              │
│        ╲ █▓░▓█ ╱                  ╲ ◠◡◠◡◠ ╱               │
│         ╰─────╯                    ╰─────╯                 │
│      Waveform animation         Spinning/loading            │
│      Voice-reactive             Purple processing           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Color Meanings

| Color | Hex | Meaning |
|-------|-----|---------|
| Blue | #3b82f6 | Idle, neutral |
| Cyan | #06b6d4 | Listening, attentive |
| Purple | #8b5cf6 | Thinking, processing |
| Green | #10b981 | Success, positive |
| Orange | #f59e0b | Warning, alert |
| Red | #ef4444 | Critical, error |

### Animation Specs

**Idle Pulse:**
- Scale: 1.0 → 1.05 → 1.0
- Duration: 2s
- Easing: ease-in-out
- Opacity: 0.7 → 1.0 → 0.7

**Listening Expansion:**
- Scale: 1.0 → 1.2
- Duration: 0.3s
- Ripple rings emanating outward
- Glow intensity increases

**Speaking Waveform:**
- Audio-reactive scaling
- Multiple concentric rings
- Wave distortion effect
- Synced to voice amplitude

**Thinking Rotation:**
- Particle orbit around core
- Subtle spin
- Loading indicator

---

## Implementation: Three.js Orb

### Component Structure

```tsx
// components/jarvis/JarvisOrb.tsx

interface JarvisOrbProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking';
  audioData?: Float32Array;  // For waveform visualization
  color?: string;
}

export function JarvisOrb({ state, audioData, color }: JarvisOrbProps) {
  // Three.js canvas with custom shader
  // Responds to state changes
  // Audio-reactive when speaking
}
```

### Shader Effects

```glsl
// Vertex shader for orb distortion
uniform float uTime;
uniform float uAudioLevel;
uniform float uState; // 0=idle, 1=listening, 2=thinking, 3=speaking

void main() {
  vec3 pos = position;

  // Idle breathing
  float breathe = sin(uTime * 0.5) * 0.05;
  pos *= 1.0 + breathe;

  // Audio reactivity
  if (uState == 3.0) {
    float wave = sin(position.y * 10.0 + uTime * 5.0) * uAudioLevel * 0.2;
    pos += normal * wave;
  }

  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
```

---

## Voice Integration: ElevenLabs

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      VOICE FLOW                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   USER SPEAKS                                               │
│       │                                                     │
│       ▼                                                     │
│   ┌─────────────┐    Web Speech API (free)                 │
│   │   BROWSER   │    or Whisper API (more accurate)        │
│   │   STT       │                                           │
│   └──────┬──────┘                                           │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                           │
│   │   NEXUS     │    Claude processes with full context    │
│   │   BACKEND   │    Assembles personalized response       │
│   └──────┬──────┘                                           │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐    ElevenLabs TTS                        │
│   │  ELEVENLABS │    JARVIS-like voice                     │
│   │     TTS     │    Streaming audio                       │
│   └──────┬──────┘                                           │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                           │
│   │   BROWSER   │    Play audio + animate orb              │
│   │   SPEAKER   │    Waveform visualization                │
│   └─────────────┘                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Voice Settings

**Recommended ElevenLabs Voice:**
- "Antoni" or "Adam" for JARVIS-like British-ish, professional tone
- Custom voice clone for unique identity

**Voice Settings:**
```json
{
  "voice_id": "pNInz6obpgDQGcFmaJgB",  // Adam
  "model_id": "eleven_turbo_v2",
  "voice_settings": {
    "stability": 0.75,
    "similarity_boost": 0.85,
    "style": 0.2,
    "use_speaker_boost": true
  }
}
```

### Wake Word

**"Hey Nexus"** - Triggers listening mode.

Implementation options:
1. **Porcupine** - Local wake word detection (free tier available)
2. **Browser always-on** - Listen for keyword in transcript
3. **Push-to-talk** - Keyboard shortcut (spacebar hold)

### Speech Recognition

**Option 1: Web Speech API (Free)**
```typescript
const recognition = new webkitSpeechRecognition();
recognition.continuous = false;
recognition.interimResults = true;
recognition.lang = 'en-US';
```

**Option 2: Whisper API (More Accurate)**
- Better for accents/noise
- ~$0.006 per minute
- Higher latency

---

## Backend Integration

### New Endpoints

```python
# POST /api/voice/transcribe
# Receives audio blob, returns transcript
async def transcribe_audio(audio: UploadFile) -> TranscriptResponse:
    # Use Whisper API or local Whisper
    pass

# POST /api/voice/synthesize
# Receives text, returns audio stream
async def synthesize_speech(request: SynthesizeRequest) -> StreamingResponse:
    # Use ElevenLabs API
    pass

# WebSocket /api/voice/stream
# Full duplex voice conversation
async def voice_stream(websocket: WebSocket):
    # Streaming STT → Claude → TTS
    pass
```

### ElevenLabs Integration

```python
# app/voice/elevenlabs.py

import httpx
from app.core.config import settings

class ElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.ELEVENLABS_VOICE_ID

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Stream audio chunks as they're generated."""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/text-to-speech/{self.voice_id}/stream",
                headers={"xi-api-key": self.api_key},
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2",
                    "voice_settings": {
                        "stability": 0.75,
                        "similarity_boost": 0.85
                    }
                }
            ) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
```

---

## Frontend Integration

### Voice Hook

```typescript
// hooks/useVoice.ts

export function useVoice() {
  const [state, setState] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle');
  const [transcript, setTranscript] = useState('');
  const audioContextRef = useRef<AudioContext>();
  const analyserRef = useRef<AnalyserNode>();

  const startListening = async () => {
    setState('listening');
    // Start speech recognition
  };

  const speak = async (text: string) => {
    setState('speaking');
    // Stream from ElevenLabs
    // Play audio
    // Get audio data for visualization
  };

  const getAudioData = () => {
    // Return current audio frequency data for orb animation
    if (analyserRef.current) {
      const data = new Float32Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getFloatFrequencyData(data);
      return data;
    }
    return null;
  };

  return { state, transcript, startListening, speak, getAudioData };
}
```

### Voice UI Component

```tsx
// components/jarvis/JarvisVoiceUI.tsx

export function JarvisVoiceUI() {
  const { state, transcript, startListening, getAudioData } = useVoice();

  return (
    <div className="fixed bottom-8 right-8 flex flex-col items-center">
      {/* The Orb */}
      <JarvisOrb
        state={state}
        audioData={state === 'speaking' ? getAudioData() : undefined}
      />

      {/* Transcript display */}
      {transcript && (
        <div className="mt-4 p-3 bg-surface/80 backdrop-blur rounded-lg">
          {transcript}
        </div>
      )}

      {/* Push to talk button */}
      <button
        onMouseDown={startListening}
        className="mt-4 px-4 py-2 bg-blue-500/20 border border-blue-500/50 rounded-full"
      >
        Hold to speak
      </button>
    </div>
  );
}
```

---

## Conversation Flow

### Example Interaction

```
[Orb: Idle, gentle blue pulse]

User: "Hey Nexus"

[Orb: Expands, turns cyan, rippling]
[Listens for command]

User: "What should I focus on today?"

[Orb: Contracts slightly, turns purple, spinning]
[Processing - assembling context, calling Claude]

[Orb: Turns green, waveform animation]
Nexus (voice): "Good morning. Based on your calendar and goals,
               I'd prioritize the Nexus frontend work first -
               you have a clear 4-hour block this morning and
               your energy is typically highest before noon.

               You're also on a 24-day coding streak. A focused
               session now would bring you to 25 days - a new
               personal record.

               Should I start a focus timer?"

[Orb: Returns to blue idle pulse]

User: "Yes, do it"

[Orb: Brief green flash]
Nexus (voice): "Done. 90-minute focus session started.
               I'll keep distractions away. Good luck."

[Orb: Blue idle, focus timer appears in corner]
```

---

## Dependencies

### Frontend
```json
{
  "@react-three/fiber": "^8.15.0",
  "@react-three/drei": "^9.92.0",
  "three": "^0.160.0"
}
```

### Backend
```
elevenlabs>=1.0.0
openai-whisper>=20231117  # Optional, for local STT
```

### API Keys Required
- `ELEVENLABS_API_KEY` - For text-to-speech
- ElevenLabs free tier: 10,000 characters/month
- Paid: starts at $5/month for 30,000 characters

---

## Future Enhancements

1. **Custom Voice Clone** - Train on your preferred voice
2. **Emotion Detection** - Adjust responses based on tone
3. **Ambient Awareness** - Detect environment (home/office/car)
4. **Multi-language** - Support for other languages
5. **AR Integration** - Project Nexus orb in physical space

---

*Last updated: 2026-03-19*
