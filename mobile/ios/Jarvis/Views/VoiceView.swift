import SwiftUI

struct VoiceView: View {
    @Bindable var viewModel: VoiceViewModel
    var activeMode: AgentMode = .jarvis

    var body: some View {
        NavigationStack {
            ZStack {
                Color.darkBackground.ignoresSafeArea()

                VStack(spacing: 0) {
                    Spacer()

                    // Response text (above orb)
                    responseSection
                        .padding(.bottom, 40)

                    // Animated Orb
                    voiceOrb
                        .padding(.bottom, 32)

                    // Transcription text (below orb)
                    transcriptionSection
                        .padding(.top, 8)

                    Spacer()

                    // State label
                    stateLabel
                        .padding(.bottom, 40)
                }
                .padding(.horizontal, 24)
            }
            .navigationTitle("Voice")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                viewModel.requestPermissions()
                viewModel.setMode(activeMode)
            }
            .onChange(of: activeMode) {
                viewModel.setMode(activeMode)
            }
        }
    }

    // MARK: - Voice Orb

    private var voiceOrb: some View {
        let baseSize: CGFloat = 160
        let pulseFactor = CGFloat(1.0 + Double(viewModel.audioLevel) * 0.3)
        let orbColor = viewModel.voiceState.color

        return ZStack {
            // Outer glow ring
            Circle()
                .fill(orbColor.opacity(0.08))
                .frame(width: baseSize * 1.6 * pulseFactor, height: baseSize * 1.6 * pulseFactor)

            // Mid glow ring
            Circle()
                .fill(orbColor.opacity(0.12))
                .frame(width: baseSize * 1.3 * pulseFactor, height: baseSize * 1.3 * pulseFactor)

            // Core orb
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            orbColor.opacity(0.9),
                            orbColor.opacity(0.5),
                            orbColor.opacity(0.2)
                        ],
                        center: .center,
                        startRadius: 10,
                        endRadius: baseSize / 2
                    )
                )
                .frame(width: baseSize * pulseFactor, height: baseSize * pulseFactor)
                .shadow(color: orbColor.opacity(0.6), radius: 30 + CGFloat(viewModel.audioLevel) * 20)

            // Inner bright core
            Circle()
                .fill(orbColor.opacity(0.3))
                .frame(width: baseSize * 0.4, height: baseSize * 0.4)
                .blur(radius: 10)

            // Icon overlay
            Image(systemName: orbIcon)
                .font(.system(size: 36, weight: .light))
                .foregroundStyle(.white.opacity(0.9))
        }
        .animation(.easeInOut(duration: 0.15), value: viewModel.audioLevel)
        .animation(.easeInOut(duration: 0.4), value: viewModel.voiceState)
        .onTapGesture {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                viewModel.toggleListening()
            }
        }
    }

    private var orbIcon: String {
        switch viewModel.voiceState {
        case .idle:      return "mic.fill"
        case .listening: return "waveform"
        case .thinking:  return "brain"
        case .speaking:  return "speaker.wave.2.fill"
        }
    }

    // MARK: - Response Section

    private var responseSection: some View {
        Group {
            if !viewModel.responseText.isEmpty {
                Text(viewModel.responseText)
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.9))
                    .multilineTextAlignment(.center)
                    .lineLimit(6)
                    .padding(.horizontal, 16)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .frame(minHeight: 60)
        .animation(.easeInOut(duration: 0.3), value: viewModel.responseText)
    }

    // MARK: - Transcription Section

    private var transcriptionSection: some View {
        Group {
            if !viewModel.transcribedText.isEmpty {
                Text(viewModel.transcribedText)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .padding(.horizontal, 16)
                    .transition(.opacity)
            }
        }
        .frame(minHeight: 40)
        .animation(.easeInOut(duration: 0.2), value: viewModel.transcribedText)
    }

    // MARK: - State Label

    private var stateLabel: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(viewModel.voiceState.color)
                .frame(width: 8, height: 8)

            Text(viewModel.voiceState.displayText)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .animation(.easeInOut, value: viewModel.voiceState)
    }
}

// MARK: - Preview

#Preview {
    VoiceView(viewModel: VoiceViewModel())
        .preferredColorScheme(.dark)
}
