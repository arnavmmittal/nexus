import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var chatViewModel: ChatViewModel
    @EnvironmentObject private var voiceViewModel: VoiceViewModel
    @EnvironmentObject private var settingsViewModel: SettingsViewModel

    @State private var selectedTab: Tab = .chat

    enum Tab: String, CaseIterable {
        case chat
        case voice
        case dashboard
        case settings

        var title: String {
            switch self {
            case .chat:      "Chat"
            case .voice:     "Voice"
            case .dashboard: "Dashboard"
            case .settings:  "Settings"
            }
        }

        var icon: String {
            switch self {
            case .chat:      "bubble.left.and.bubble.right.fill"
            case .voice:     "waveform.circle.fill"
            case .dashboard: "square.grid.2x2.fill"
            case .settings:  "gearshape.fill"
            }
        }
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            ForEach(Tab.allCases, id: \.self) { tab in
                tabContent(for: tab)
                    .tabItem {
                        Label(tab.title, systemImage: tab.icon)
                    }
                    .tag(tab)
            }
        }
        .tint(.white)
    }

    // MARK: - Tab Content

    @ViewBuilder
    private func tabContent(for tab: Tab) -> some View {
        switch tab {
        case .chat:
            ChatTabView()
        case .voice:
            VoiceTabView()
        case .dashboard:
            DashboardTabView()
        case .settings:
            SettingsTabView()
        }
    }
}

// MARK: - Chat Tab

struct ChatTabView: View {
    @EnvironmentObject private var chatViewModel: ChatViewModel

    var body: some View {
        NavigationStack {
            VStack {
                Spacer()
                Text("Jarvis is ready.")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemBackground))
            .navigationTitle("Jarvis")
        }
    }
}

// MARK: - Voice Tab

struct VoiceTabView: View {
    @EnvironmentObject private var voiceViewModel: VoiceViewModel

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()

                // Orb placeholder
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [.blue, .purple.opacity(0.6), .clear],
                            center: .center,
                            startRadius: 10,
                            endRadius: 80
                        )
                    )
                    .frame(width: 160, height: 160)
                    .shadow(color: .blue.opacity(0.5), radius: 30)

                Text("Tap to speak")
                    .font(.headline)
                    .foregroundStyle(.secondary)

                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemBackground))
            .navigationTitle("Voice")
        }
    }
}

// MARK: - Dashboard Tab

struct DashboardTabView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVGrid(
                    columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ],
                    spacing: 16
                ) {
                    DashboardCard(title: "Tasks", value: "--", icon: "checklist")
                    DashboardCard(title: "Messages", value: "--", icon: "envelope.fill")
                    DashboardCard(title: "Calendar", value: "--", icon: "calendar")
                    DashboardCard(title: "Notes", value: "--", icon: "note.text")
                }
                .padding()
            }
            .background(Color(.systemBackground))
            .navigationTitle("Dashboard")
        }
    }
}

struct DashboardCard: View {
    let title: String
    let value: String
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(.blue)

            Text(value)
                .font(.title)
                .fontWeight(.bold)

            Text(title)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Settings Tab

struct SettingsTabView: View {
    @EnvironmentObject private var settingsViewModel: SettingsViewModel

    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    Label("Profile", systemImage: "person.crop.circle")
                    Label("Backend Server", systemImage: "server.rack")
                }

                Section("Preferences") {
                    Label("Voice", systemImage: "mic.fill")
                    Label("Notifications", systemImage: "bell.fill")
                    Label("Appearance", systemImage: "paintbrush.fill")
                }

                Section("About") {
                    Label("Version", systemImage: "info.circle")
                    Label("Privacy Policy", systemImage: "hand.raised.fill")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
        .environmentObject(VoiceViewModel())
        .environmentObject(SettingsViewModel())
        .preferredColorScheme(.dark)
}
