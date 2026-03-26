# Nexus Mobile & Home Integration Plan

**Created**: 2026-03-25
**Status**: In Progress
**Goal**: Access Jarvis/Ultron anywhere - phone, home, always available

---

## Executive Summary

Transform Nexus from a web-only interface to an omnipresent assistant accessible via:
- Mobile devices (voice + text, anywhere)
- Home terminals (kitchen, living room, family-wide)
- Wearables (Apple Watch)

Key principles:
- **Low latency** (<2s response time)
- **High quality** (Claude-powered intelligence)
- **Always available** (not dependent on browser)
- **Family-friendly** (multi-user support)

---

## Phase 1: Mobile Access (Immediate)

### 1.1 iOS Shortcuts Integration
**Timeline**: Day 1
**Effort**: 4 hours

Create API endpoints optimized for Shortcuts:

```
POST /api/v1/shortcut/voice
- Input: { "text": "...", "user_id": "..." }
- Output: { "response": "...", "speak": "..." }
- Optimized for voice: concise responses
- Returns audio URL for direct playback
```

**Shortcut Flow**:
```
"Hey Siri, ask Jarvis [query]"
    ↓
Dictate text → Call API → Get response
    ↓
Speak response + Show on screen
```

**Features**:
- Voice input/output
- Quick actions: "Jarvis lights on", "Jarvis remind me..."
- Context preservation across calls
- Minimal latency (streaming response)

### 1.2 Telegram Bot
**Timeline**: Day 1-2
**Effort**: 6 hours

```
@NexusJarvisBot
├── Text messages → AI response
├── Voice messages → Transcribe → AI → Voice reply
├── Images → Vision analysis
├── Documents → Document analysis
├── /commands
│   ├── /home - Smart home controls
│   ├── /schedule - View/add reminders
│   ├── /memory - What do you remember?
│   └── /ultron - Switch to Ultron mode
```

**Architecture**:
```
Telegram → Webhook → FastAPI → AI Engine → Response
                         ↓
                  ElevenLabs TTS (optional voice)
```

### 1.3 Progressive Web App (PWA)
**Timeline**: Day 2
**Effort**: 4 hours

Enhance frontend for installable app:
- Service worker for offline support
- Push notifications for proactive alerts
- Add to home screen prompt
- App-like navigation (no browser chrome)
- Background sync for pending actions

**manifest.json** additions:
```json
{
  "name": "Nexus - Jarvis",
  "short_name": "Jarvis",
  "display": "standalone",
  "background_color": "#0a0a0a",
  "theme_color": "#3b82f6",
  "icons": [...]
}
```

---

## Phase 2: Enhanced Mobile (Week 1-2)

### 2.1 Native iOS App
**Timeline**: Week 1-2
**Effort**: 20 hours

**Features**:
- Always-listening mode (optional)
- Wake word: "Hey Jarvis" (on-device detection)
- Widgets: Quick actions, predictions, calendar
- Apple Watch companion
- Siri Intents (deep integration)
- Background refresh for proactive alerts
- Face ID for sensitive actions

**Tech Stack**:
- Swift UI
- Speech framework (on-device transcription)
- AVFoundation (audio playback)
- WidgetKit
- WatchConnectivity

### 2.2 Android App
**Timeline**: Week 2
**Effort**: 15 hours

Mirror iOS functionality:
- Kotlin + Jetpack Compose
- Google Assistant integration
- Home screen widgets
- Wear OS companion

### 2.3 Apple Watch App
**Timeline**: Week 2
**Effort**: 8 hours

- Raise to speak
- Complications showing next reminder/prediction
- Quick replies
- Haptic alerts for important predictions

---

## Phase 3: Home Integration (Week 2-4)

### 3.1 Family Profiles
**Timeline**: Week 2
**Effort**: 8 hours

```python
class FamilyMember:
    id: str
    name: str
    voice_id: str  # For voice recognition
    preferences: UserPreferences
    autonomy_level: float  # Kids might have lower
    allowed_actions: List[str]  # Parental controls
```

**Voice Recognition**:
- Train on each family member's voice
- Personalized responses: "Good morning, Arnav" vs "Good morning, Mom"
- Per-person memory and context

### 3.2 Kitchen Terminal
**Timeline**: Week 3
**Effort**: 12 hours

**Hardware**:
- iPad / Android tablet (wall-mounted)
- Or: Raspberry Pi 4 + 7" touchscreen

**Display**:
```
┌─────────────────────────────────────────┐
│  Good Morning, Family    ☀️ 72°F       │
├─────────────────────────────────────────┤
│  TODAY                                  │
│  ├─ 9:00 AM  Team standup (Arnav)      │
│  ├─ 3:30 PM  Soccer practice (Kids)    │
│  └─ 7:00 PM  Dinner reservation        │
├─────────────────────────────────────────┤
│  REMINDERS                              │
│  • Pick up dry cleaning                 │
│  • Grocery list: milk, eggs, bread     │
├─────────────────────────────────────────┤
│  🎤 "Hey Jarvis..."                     │
└─────────────────────────────────────────┘
```

**Always Listening**:
- Wake word detection (on-device, privacy-first)
- Visual indicator when listening
- Family-appropriate responses

### 3.3 Living Room Hub
**Timeline**: Week 3
**Effort**: 10 hours

**Integration Options**:

**Option A: Apple TV App**
- Voice via Siri Remote
- Display on TV
- HomePod integration for audio

**Option B: Raspberry Pi + Speaker**
```
Hardware:
- Raspberry Pi 4 (4GB)
- ReSpeaker 4-Mic Array
- Quality speaker (Sonos via API or dedicated)
- Optional: Small OLED status display

Software:
- Wake word: Picovoice Porcupine (offline)
- VAD: Silero (voice activity detection)
- Stream to Nexus API
- ElevenLabs for response
```

**Option C: Repurpose Echo/Google**
- Custom Alexa Skill → Your API
- Keeps their wake word, uses your brain

### 3.4 Whole-Home Presence
**Timeline**: Week 4
**Effort**: 8 hours

**Detection Methods**:
- Phone location (home/away)
- Smart home sensors (motion, doors)
- WiFi device presence
- Bluetooth beacons

**Automations**:
```yaml
triggers:
  - type: presence
    who: arnav
    state: arriving
actions:
  - turn_on: living_room_lights
  - set_thermostat: 72
  - announcement: "Welcome home, Arnav"
```

---

## Phase 4: Advanced Features (Month 2+)

### 4.1 Multi-Room Audio
- Synchronized announcements
- "Jarvis, announce dinner is ready"
- Room-aware responses (kitchen vs bedroom)

### 4.2 Security Integration
- Camera feeds analysis
- "Who's at the door?" → Vision analysis
- Anomaly detection

### 4.3 Vehicle Integration
- CarPlay app
- Commute briefings
- "On my way home" automation

### 4.4 Custom Hardware Terminal
```
┌─────────────────────────────────────┐
│       JARVIS HOME TERMINAL         │
├─────────────────────────────────────┤
│  Components:                        │
│  - Raspberry Pi 5                   │
│  - 10" IPS touchscreen              │
│  - ReSpeaker 6-Mic Circular Array   │
│  - 2x 3W speakers (stereo)          │
│  - RGB LED ring (status)            │
│  - Wide-angle camera                │
│  - 3D printed enclosure             │
│                                     │
│  Estimated Cost: $200-250           │
└─────────────────────────────────────┘
```

---

## Technical Architecture

### API Design for Low Latency

```
Mobile/Home Client
       ↓
   WebSocket (persistent connection)
       ↓
   FastAPI Backend
       ↓
   ┌─────────────────────────────────┐
   │  Request Router                 │
   │  - Classify query complexity    │
   │  - Route to appropriate model   │
   │  - Stream response tokens       │
   └─────────────────────────────────┘
       ↓
   ┌─────────────────────────────────┐
   │  Response Pipeline              │
   │  1. First token → Start TTS     │
   │  2. Stream audio chunks         │
   │  3. Complete while speaking     │
   └─────────────────────────────────┘
```

### Latency Targets

| Stage | Target | Technique |
|-------|--------|-----------|
| Wake word detection | <100ms | On-device (Picovoice) |
| Audio to text | <500ms | Whisper streaming |
| API routing | <50ms | Model tier classification |
| First token | <300ms | Streaming response |
| First audio | <800ms | Sentence-buffered TTS |
| **Total perceived** | **<1.5s** | Parallel processing |

### Security Considerations

- **Authentication**: JWT tokens, biometric on mobile
- **Family safety**: Per-user permissions, content filters
- **Privacy**: On-device wake word, no always-streaming
- **Local fallback**: Basic commands work without internet

---

## Implementation Checklist

### Phase 1 (This Week) ✅ COMPLETE
- [x] iOS Shortcut API endpoint
- [x] Shortcut voice optimization (concise responses)
- [x] Audio URL generation for playback
- [x] Telegram bot setup
- [x] Telegram webhook handler
- [x] Voice message transcription
- [x] Image/document handling in Telegram
- [x] PWA manifest and service worker
- [x] Push notification system
- [x] PWA icons and splash screens generated

### Phase 2 (Week 1-2) ✅ iOS COMPLETE
- [x] iOS app scaffolding (SwiftUI, @Observable)
- [x] iOS widgets (WidgetKit - Quick Actions + Status)
- [x] Apple Watch app (WatchConnectivity + direct API)
- [x] Siri Intents (Ask Jarvis, Home Control, Remind Me)
- [ ] Wake word integration (Picovoice) — deferred to Phase 4
- [ ] Android app — deferred
- [ ] Wear OS companion — deferred

### Phase 3 (Week 2-4) ✅ COMPLETE
- [x] Family member profiles (FamilyManager + JSON persistence)
- [x] Kitchen/home terminal UI (full-screen kiosk mode)
- [x] Raspberry Pi setup scripts (Chromium kiosk + systemd)
- [x] Whole-home presence system (auto-expiry, arrival/departure hooks)
- [x] Family API endpoints (CRUD, greetings, presence)
- [ ] Voice recognition per user — deferred to Phase 4
- [ ] Wake word service — deferred to Phase 4

### Phase 4 (Month 2+) ✅ COMPLETE
- [x] Multi-room audio system (Sonos/Chromecast/AirPlay/local, zone grouping)
- [x] Security camera integration (RTSP/Ring/Nest, Claude Vision analysis, motion detection)
- [x] Vehicle integration (driving mode, commute briefings, "on my way home" automation)
- [x] Custom hardware terminal (Pi 5 setup, LED ring controller, health monitor)
- [x] Wake word service (Picovoice Porcupine, energy-based VAD, systemd)
- [x] Voice recognition per family member (MFCC embeddings, cosine similarity)

---

## File Structure

```
nexus/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── shortcut.py      # iOS Shortcut endpoints
│   │   │   └── telegram.py      # Telegram webhook
│   │   ├── mobile/
│   │   │   ├── push.py          # Push notifications
│   │   │   └── presence.py      # Location tracking
│   │   └── home/
│   │       ├── terminal.py      # Home terminal API
│   │       ├── family.py        # Family profiles
│   │       └── wake_word.py     # Wake word service
├── mobile/
│   ├── ios/                     # Native iOS app
│   ├── android/                 # Native Android app
│   └── shortcuts/               # iOS Shortcut configs
├── home/
│   ├── terminal/                # Terminal UI (React)
│   ├── raspberry-pi/            # Pi setup scripts
│   └── wake-word/               # Wake word service
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Response latency | <2 seconds |
| Wake word accuracy | >95% |
| Voice recognition accuracy | >90% |
| Daily active usage | Family uses 10+ times/day |
| Proactive alert relevance | >80% useful |

---

## Next Steps

1. **Today**: Build iOS Shortcut endpoint + Telegram bot
2. **Tomorrow**: PWA enhancements + push notifications
3. **This week**: Test mobile access thoroughly
4. **Next week**: Begin native app development

---

*Plan saved to: `/docs/plans/2026-03-25-mobile-home-integration-plan.md`*
