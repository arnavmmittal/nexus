import SwiftUI

/// A large, glanceable driving-mode UI designed for minimal distraction.
struct DrivingView: View {
    @State private var isDriving = false
    @State private var briefingSummary: String = "Tap Start Driving to begin."
    @State private var eta: String? = nil
    @State private var nextEvent: String? = nil
    @State private var isLoadingBriefing = false
    @State private var showOnMyWayConfirmation = false

    var onDismiss: (() -> Void)?
    var onVoiceTap: (() -> Void)?

    var body: some View {
        ZStack {
            Color.darkBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // MARK: - Top bar
                topBar
                    .padding(.horizontal, 24)
                    .padding(.top, 16)

                Spacer()

                // MARK: - Briefing Card
                briefingCard
                    .padding(.horizontal, 24)

                Spacer()

                // MARK: - Voice Button
                voiceButton
                    .padding(.bottom, 28)

                // MARK: - Quick Actions
                quickActions
                    .padding(.horizontal, 24)
                    .padding(.bottom, 40)
            }
        }
        .preferredColorScheme(.dark)
        .overlay {
            if showOnMyWayConfirmation {
                onMyWayConfirmation
                    .transition(.opacity.combined(with: .scale))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: showOnMyWayConfirmation)
    }

    // MARK: - Top Bar

    private var topBar: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Driving Mode")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)

                HStack(spacing: 6) {
                    Circle()
                        .fill(isDriving ? Color.emerald : .gray)
                        .frame(width: 8, height: 8)

                    Text(isDriving ? "Active" : "Inactive")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button {
                onDismiss?()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Briefing Card

    private var briefingCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Summary
            Text(briefingSummary)
                .font(.title3)
                .fontWeight(.medium)
                .foregroundStyle(.white)
                .lineLimit(5)
                .fixedSize(horizontal: false, vertical: true)

            // ETA Row
            if let eta {
                HStack(spacing: 10) {
                    Image(systemName: "clock.fill")
                        .font(.title3)
                        .foregroundStyle(.emerald)

                    Text("ETA: \(eta)")
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                }
            }

            // Next event
            if let nextEvent {
                HStack(spacing: 10) {
                    Image(systemName: "calendar")
                        .font(.title3)
                        .foregroundStyle(.amber)

                    Text(nextEvent)
                        .font(.body)
                        .foregroundStyle(.white.opacity(0.85))
                        .lineLimit(2)
                }
            }

            if isLoadingBriefing {
                HStack {
                    Spacer()
                    ProgressView()
                        .tint(.emerald)
                    Spacer()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(24)
        .background(Color.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 20))
    }

    // MARK: - Voice Button

    private var voiceButton: some View {
        Button {
            onVoiceTap?()
        } label: {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                Color.emerald.opacity(0.9),
                                Color.emerald.opacity(0.4),
                                Color.emerald.opacity(0.1)
                            ],
                            center: .center,
                            startRadius: 10,
                            endRadius: 50
                        )
                    )
                    .frame(width: 100, height: 100)
                    .shadow(color: .emerald.opacity(0.5), radius: 20)

                Image(systemName: "mic.fill")
                    .font(.system(size: 32, weight: .medium))
                    .foregroundStyle(.white)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Voice command")
    }

    // MARK: - Quick Actions

    private var quickActions: some View {
        HStack(spacing: 16) {
            // Start / Stop Driving
            drivingToggleButton

            // On My Way Home
            onMyWayHomeButton

            // Refresh Briefing
            refreshBriefingButton
        }
    }

    private var drivingToggleButton: some View {
        Button {
            Task {
                if isDriving {
                    await stopDriving()
                } else {
                    await startDriving()
                }
            }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: isDriving ? "stop.circle.fill" : "car.fill")
                    .font(.title2)
                    .foregroundStyle(isDriving ? .red : .emerald)

                Text(isDriving ? "Stop" : "Start")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    private var onMyWayHomeButton: some View {
        Button {
            Task { await triggerOnMyWayHome() }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: "house.fill")
                    .font(.title2)
                    .foregroundStyle(.amber)

                Text("Home")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    private var refreshBriefingButton: some View {
        Button {
            Task { await loadBriefing() }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: "arrow.clockwise.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.blue)

                Text("Refresh")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    // MARK: - On My Way Confirmation Overlay

    private var onMyWayConfirmation: some View {
        ZStack {
            Color.black.opacity(0.6)
                .ignoresSafeArea()
                .onTapGesture {
                    showOnMyWayConfirmation = false
                }

            VStack(spacing: 20) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(.emerald)

                Text("On My Way Home")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)

                Text("Home is being prepared for your arrival.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Button("OK") {
                    showOnMyWayConfirmation = false
                }
                .font(.headline)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.emerald)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .padding(32)
            .background(Color.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 24))
            .padding(.horizontal, 40)
        }
    }

    // MARK: - Actions

    private func startDriving() async {
        await VehicleService.shared.startDrivingMode()
        isDriving = true
        await loadBriefing()
    }

    private func stopDriving() async {
        await VehicleService.shared.stopDrivingMode()
        isDriving = false
        briefingSummary = "Driving ended. Have a good one."
        eta = nil
        nextEvent = nil
    }

    private func loadBriefing() async {
        isLoadingBriefing = true
        defer { isLoadingBriefing = false }

        do {
            let briefing = try await VehicleService.shared.generateBriefing()
            briefingSummary = briefing.summary
            eta = briefing.estimatedArrival
            nextEvent = briefing.calendarEvents.first
        } catch {
            briefingSummary = "Could not load briefing. Check connection."
        }
    }

    private func triggerOnMyWayHome() async {
        do {
            _ = try await VehicleService.shared.onMyWayHome()
            showOnMyWayConfirmation = true
        } catch {
            briefingSummary = "Failed to trigger home automation."
        }
    }
}

// MARK: - Preview

#Preview {
    DrivingView()
        .preferredColorScheme(.dark)
}
