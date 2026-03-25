import SwiftUI

/// Main Watch interface - voice-first with quick actions.
struct WatchHomeView: View {
    @State private var viewModel = WatchViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Voice orb - tap to speak
                    VoiceOrbView(
                        state: viewModel.voiceState,
                        audioLevel: viewModel.audioLevel
                    )
                    .onTapGesture {
                        Task { await viewModel.toggleListening() }
                    }

                    // Transcription / Response
                    if !viewModel.displayText.isEmpty {
                        Text(viewModel.displayText)
                            .font(.body)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(viewModel.voiceState == .speaking ? .green : .white)
                            .padding(.horizontal, 8)
                            .lineLimit(4)
                    }

                    // Quick actions
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                        QuickActionButton(icon: "lightbulb.fill", label: "Lights") {
                            Task { await viewModel.quickAction("lights_on") }
                        }
                        QuickActionButton(icon: "thermometer.medium", label: "Status") {
                            Task { await viewModel.quickAction("status") }
                        }
                        QuickActionButton(icon: "bell.fill", label: "Remind") {
                            Task { await viewModel.quickAction("remind") }
                        }
                        QuickActionButton(icon: "house.fill", label: "Home") {
                            Task { await viewModel.quickAction("home_status") }
                        }
                    }
                }
                .padding(.top, 8)
            }
            .navigationTitle("Jarvis")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Voice Orb for Watch

struct VoiceOrbView: View {
    let state: WatchVoiceState
    let audioLevel: Float

    var orbColor: Color {
        switch state {
        case .idle: return Color(hex: "3b82f6")
        case .listening: return Color(hex: "10b981")
        case .thinking: return Color(hex: "f59e0b")
        case .speaking: return Color(hex: "10b981")
        }
    }

    var body: some View {
        ZStack {
            // Glow
            Circle()
                .fill(orbColor.opacity(0.2))
                .frame(width: 80 + CGFloat(audioLevel) * 20,
                       height: 80 + CGFloat(audioLevel) * 20)
                .animation(.easeInOut(duration: 0.1), value: audioLevel)

            // Main orb
            Circle()
                .fill(orbColor)
                .frame(width: 60, height: 60)

            // State icon
            Image(systemName: stateIcon)
                .font(.title2)
                .foregroundStyle(.black)
        }
    }

    var stateIcon: String {
        switch state {
        case .idle: return "waveform"
        case .listening: return "mic.fill"
        case .thinking: return "ellipsis"
        case .speaking: return "speaker.wave.2.fill"
        }
    }
}

// MARK: - Quick Action Button

struct QuickActionButton: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.title3)
                Text(label)
                    .font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
        }
        .buttonStyle(.bordered)
        .tint(Color(hex: "10b981"))
    }
}

// MARK: - Color Extension (Watch)

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8) & 0xFF) / 255
        let b = Double(int & 0xFF) / 255
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1)
    }
}
