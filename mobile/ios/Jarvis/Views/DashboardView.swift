import SwiftUI

struct DashboardView: View {
    var activeMode: AgentMode = .jarvis
    var onNavigateToChat: (() -> Void)?
    var onNavigateToVoice: (() -> Void)?

    @State private var recentConversations: [ConversationSummary] = []

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: .now)
        switch hour {
        case 5..<12:  return "Good morning"
        case 12..<17: return "Good afternoon"
        case 17..<22: return "Good evening"
        default:      return "Good night"
        }
    }

    private var quickActions: [QuickAction] {
        [
            QuickAction(
                title: "Talk to Jarvis",
                icon: "waveform.circle.fill",
                color: .emerald,
                action: .talkToJarvis
            ),
            QuickAction(
                title: "Lights",
                icon: "lightbulb.fill",
                color: .amber,
                action: .lights
            ),
            QuickAction(
                title: "Status",
                icon: "chart.bar.fill",
                color: .blue,
                action: .status
            ),
            QuickAction(
                title: "Remind Me",
                icon: "bell.badge.fill",
                color: .purple,
                action: .remindMe
            ),
        ]
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    greetingSection
                    quickActionsGrid
                    recentSection
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 24)
            }
            .background(Color.darkBackground)
            .navigationTitle("Dashboard")
            .navigationBarTitleDisplayMode(.large)
        }
    }

    // MARK: - Greeting

    private var greetingSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(greeting)
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            Text("\(activeMode.displayName) is standing by.")
                .font(.body)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 8)
    }

    // MARK: - Quick Actions

    private var quickActionsGrid: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Quick Actions")
                .font(.headline)
                .foregroundStyle(.secondary)

            LazyVGrid(
                columns: [
                    GridItem(.flexible(), spacing: 14),
                    GridItem(.flexible(), spacing: 14)
                ],
                spacing: 14
            ) {
                ForEach(quickActions) { action in
                    QuickActionCard(action: action) {
                        handleAction(action.action)
                    }
                }
            }
        }
    }

    // MARK: - Recent Conversations

    private var recentSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Recent")
                .font(.headline)
                .foregroundStyle(.secondary)

            if recentConversations.isEmpty {
                emptyRecentState
            } else {
                ForEach(recentConversations) { conversation in
                    RecentConversationRow(conversation: conversation)
                }
            }
        }
    }

    private var emptyRecentState: some View {
        HStack(spacing: 12) {
            Image(systemName: "bubble.left.and.text.bubble.right")
                .font(.title2)
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 2) {
                Text("No recent conversations")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text("Start chatting or use voice to get going.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - Actions

    private func handleAction(_ type: QuickActionType) {
        switch type {
        case .talkToJarvis:
            onNavigateToVoice?()
        case .lights:
            break // TODO: integrate smart home
        case .status:
            break // TODO: show system status
        case .remindMe:
            break // TODO: open reminder flow
        }
    }
}

// MARK: - Quick Action Card

struct QuickActionCard: View {
    let action: QuickAction
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 14) {
                Image(systemName: action.icon)
                    .font(.title2)
                    .foregroundStyle(action.color)

                Text(action.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(Color.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Recent Conversation Row

struct RecentConversationRow: View {
    let conversation: ConversationSummary

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(conversation.mode.color.opacity(0.2))
                .frame(width: 40, height: 40)
                .overlay {
                    Image(systemName: conversation.mode.icon)
                        .font(.system(size: 14))
                        .foregroundStyle(conversation.mode.color)
                }

            VStack(alignment: .leading, spacing: 2) {
                Text(conversation.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .lineLimit(1)

                Text(conversation.lastMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            Text(conversation.timestamp, style: .relative)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(12)
        .background(Color.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

// MARK: - Preview

#Preview {
    DashboardView()
        .preferredColorScheme(.dark)
}
