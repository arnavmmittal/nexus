import SwiftUI

struct SettingsView: View {

    // MARK: - Persisted Settings

    @AppStorage("serverURL") private var serverURL: String = "http://localhost:8000"
    @AppStorage("apiKey") private var apiKey: String = ""
    @AppStorage("autoListen") private var autoListen: Bool = false
    @AppStorage("voiceFeedback") private var voiceFeedback: Bool = true
    @AppStorage("defaultMode") private var defaultMode: String = AgentMode.jarvis.rawValue

    // MARK: - Local State

    @State private var showingAPIKey: Bool = false
    @State private var showingResetAlert: Bool = false

    var body: some View {
        NavigationStack {
            List {
                serverSection
                securitySection
                voiceSection
                modeSection
                aboutSection
                dangerZone
            }
            .scrollContentBackground(.hidden)
            .background(Color.darkBackground)
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
        }
    }

    // MARK: - Server Section

    private var serverSection: some View {
        Section {
            HStack(spacing: 12) {
                Image(systemName: "server.rack")
                    .foregroundStyle(.emerald)
                    .frame(width: 24)

                TextField("Server URL", text: $serverURL)
                    .textContentType(.URL)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }
        } header: {
            Text("Server")
        } footer: {
            Text("The URL of your Nexus backend (e.g. https://api.example.com)")
        }
    }

    // MARK: - Security Section

    private var securitySection: some View {
        Section {
            HStack(spacing: 12) {
                Image(systemName: "key.fill")
                    .foregroundStyle(.amber)
                    .frame(width: 24)

                if showingAPIKey {
                    TextField("API Key", text: $apiKey)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                } else {
                    SecureField("API Key", text: $apiKey)
                }

                Button {
                    showingAPIKey.toggle()
                } label: {
                    Image(systemName: showingAPIKey ? "eye.slash.fill" : "eye.fill")
                        .foregroundStyle(.secondary)
                        .font(.subheadline)
                }
                .buttonStyle(.plain)
            }
        } header: {
            Text("Authentication")
        } footer: {
            Text("Bearer token used to authenticate with the Nexus API.")
        }
    }

    // MARK: - Voice Section

    private var voiceSection: some View {
        Section {
            Toggle(isOn: $autoListen) {
                Label {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Auto-Listen")
                        Text("Start listening when voice tab opens")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                } icon: {
                    Image(systemName: "mic.badge.plus")
                        .foregroundStyle(.emerald)
                }
            }
            .tint(.emerald)

            Toggle(isOn: $voiceFeedback) {
                Label {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Voice Feedback")
                        Text("Speak responses aloud")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                } icon: {
                    Image(systemName: "speaker.wave.2.fill")
                        .foregroundStyle(.emerald)
                }
            }
            .tint(.emerald)
        } header: {
            Text("Voice")
        }
    }

    // MARK: - Mode Section

    private var modeSection: some View {
        Section {
            Picker(selection: $defaultMode) {
                ForEach(AgentMode.allCases, id: \.rawValue) { mode in
                    HStack {
                        Image(systemName: mode.icon)
                        Text(mode.displayName)
                    }
                    .tag(mode.rawValue)
                }
            } label: {
                Label {
                    Text("Default Mode")
                } icon: {
                    Image(systemName: "brain.head.profile")
                        .foregroundStyle(.emerald)
                }
            }
        } header: {
            Text("Agent Mode")
        } footer: {
            Text("Jarvis is helpful and conversational. Ultron is autonomous and action-oriented.")
        }
    }

    // MARK: - About Section

    private var aboutSection: some View {
        Section {
            HStack {
                Label("Version", systemImage: "info.circle")
                    .foregroundStyle(.white)
                Spacer()
                Text("1.0.0")
                    .foregroundStyle(.secondary)
            }

            HStack {
                Label("Build", systemImage: "hammer.fill")
                    .foregroundStyle(.white)
                Spacer()
                Text("2026.03")
                    .foregroundStyle(.secondary)
            }

            Link(destination: URL(string: "https://github.com/arnavmmittal/nexus")!) {
                Label("Source Code", systemImage: "chevron.left.forwardslash.chevron.right")
                    .foregroundStyle(.white)
            }
        } header: {
            Text("About")
        }
    }

    // MARK: - Danger Zone

    private var dangerZone: some View {
        Section {
            Button(role: .destructive) {
                showingResetAlert = true
            } label: {
                Label("Reset All Settings", systemImage: "arrow.counterclockwise")
            }
            .alert("Reset Settings", isPresented: $showingResetAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Reset", role: .destructive) {
                    resetSettings()
                }
            } message: {
                Text("This will reset all settings to their default values. This cannot be undone.")
            }
        }
    }

    // MARK: - Reset

    private func resetSettings() {
        serverURL = "http://localhost:8000"
        apiKey = ""
        autoListen = false
        voiceFeedback = true
        defaultMode = AgentMode.jarvis.rawValue
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .preferredColorScheme(.dark)
}
