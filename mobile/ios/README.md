# Jarvis iOS App

Native iOS app for the Nexus AI life operating system.

## Targets

| Target | Platform | Description |
|--------|----------|-------------|
| Jarvis | iOS 17+ | Main app: chat, voice, dashboard |
| JarvisWatch | watchOS 10+ | Watch companion: voice, quick actions |
| JarvisWidgets | iOS 17+ | Home screen & lock screen widgets |

## Setup

### Prerequisites
- Xcode 15+
- iOS 17+ device or simulator
- Nexus backend running (localhost:8000 or deployed)

### Xcode Project

1. Open Xcode and create a new project:
   - Template: Multiplatform → App
   - Product Name: Jarvis
   - Team: Your development team
   - Bundle Identifier: com.nexus.jarvis

2. Add existing files from this directory structure

3. Add targets:
   - Watch App: JarvisWatch
   - Widget Extension: JarvisWidgets

4. Configure signing & capabilities:
   - Push Notifications
   - Siri
   - Background Modes (audio, remote-notification, processing)
   - App Groups (for widget data sharing)

### Configuration

On first launch, go to Settings tab and configure:
- **Server URL**: Your Nexus backend URL
- **API Key**: Generate one via `POST /api/shortcut/generate-key`

## Architecture

```
Jarvis/
├── JarvisApp.swift          # App entry point
├── ContentView.swift        # Tab navigation
├── Views/
│   ├── ChatView.swift       # Text chat interface
│   ├── VoiceView.swift      # Voice-first interface
│   ├── DashboardView.swift  # Quick status & actions
│   └── SettingsView.swift   # Configuration
├── ViewModels/
│   ├── ChatViewModel.swift  # Chat state management
│   └── VoiceViewModel.swift # Voice state management
├── Services/
│   ├── NexusAPI.swift       # Backend API client
│   ├── SpeechService.swift  # On-device speech recognition
│   └── KeychainService.swift # Secure storage
├── Models/
│   ├── APIModels.swift      # Backend response types
│   └── AppModels.swift      # UI state types
└── Intents/
    ├── AskJarvisIntent.swift      # "Hey Siri, ask Jarvis..."
    └── JarvisResponseSnippet.swift # Siri response UI

JarvisWatch/
├── JarvisWatchApp.swift     # Watch app entry
├── WatchViewModel.swift     # Watch state (WatchConnectivity)
└── Views/
    └── WatchHomeView.swift  # Voice orb + quick actions

JarvisWidgets/
└── JarvisWidgets.swift      # Quick Actions + Status widgets
```

## Siri Shortcuts

The app registers these phrases:
- "Ask Jarvis [question]"
- "Hey Jarvis [question]"
- "Jarvis lights on/off"
- "Jarvis remind me [text]"
