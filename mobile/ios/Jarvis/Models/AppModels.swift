import SwiftUI

// MARK: - Agent Mode

enum AgentMode: String, CaseIterable, Codable {
    case jarvis
    case ultron

    var displayName: String {
        switch self {
        case .jarvis: "Jarvis"
        case .ultron: "Ultron"
        }
    }

    var color: Color {
        switch self {
        case .jarvis: Color(hex: 0x10B981) // emerald
        case .ultron: Color(hex: 0xEF4444) // red
        }
    }

    var icon: String {
        switch self {
        case .jarvis: "shield.checkered"
        case .ultron: "bolt.shield.fill"
        }
    }

    var tagline: String {
        switch self {
        case .jarvis: "At your service."
        case .ultron: "Autonomous mode engaged."
        }
    }
}

// MARK: - Voice State

enum VoiceState: String {
    case idle
    case listening
    case thinking
    case speaking

    var displayText: String {
        switch self {
        case .idle:      "Tap to speak"
        case .listening: "Listening..."
        case .thinking:  "Thinking..."
        case .speaking:  "Speaking..."
        }
    }

    var color: Color {
        switch self {
        case .idle:      .blue
        case .listening: Color(hex: 0x10B981) // emerald
        case .thinking:  Color(hex: 0xF59E0B) // amber
        case .speaking:  Color(hex: 0x10B981) // emerald
        }
    }
}

// MARK: - Chat Message

struct ChatMessage: Identifiable, Equatable {
    let id: String
    let role: Role
    var content: String
    let timestamp: Date
    let mode: AgentMode

    enum Role: String, Codable {
        case user
        case assistant
        case system
    }

    init(
        id: String = UUID().uuidString,
        role: Role,
        content: String,
        timestamp: Date = .now,
        mode: AgentMode = .jarvis
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.mode = mode
    }

    var isUser: Bool { role == .user }

    var bubbleColor: Color {
        switch role {
        case .user:
            return Color(.systemGray5)
        case .assistant:
            return mode.color.opacity(0.15)
        case .system:
            return Color(.systemGray6)
        }
    }

    var textColor: Color {
        switch role {
        case .user:      return .white
        case .assistant: return .white
        case .system:    return .secondary
        }
    }
}

// MARK: - Quick Action

struct QuickAction: Identifiable {
    let id = UUID()
    let title: String
    let icon: String
    let color: Color
    let action: QuickActionType
}

enum QuickActionType {
    case talkToJarvis
    case lights
    case status
    case remindMe
}

// MARK: - Conversation Summary

struct ConversationSummary: Identifiable {
    let id: String
    let title: String
    let lastMessage: String
    let timestamp: Date
    let mode: AgentMode
}

// MARK: - Color Extension

extension Color {
    init(hex: UInt, opacity: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }

    static let emerald = Color(hex: 0x10B981)
    static let ultronRed = Color(hex: 0xEF4444)
    static let amber = Color(hex: 0xF59E0B)
    static let darkBackground = Color(hex: 0x0F1117)
    static let cardBackground = Color(hex: 0x1A1D27)
}
