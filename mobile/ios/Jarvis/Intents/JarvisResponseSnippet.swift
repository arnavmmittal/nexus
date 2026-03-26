import SwiftUI

/// Visual snippet shown in Siri after asking Jarvis a question.
/// Shows the response text with Jarvis branding.
struct JarvisResponseSnippet: View {
    let response: VoiceResponse

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(hex: "10b981"))
                    .frame(width: 12, height: 12)
                Text("Jarvis")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(response.latencyMs)ms")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Text(response.text)
                .font(.body)
                .foregroundStyle(.white)
                .lineLimit(8)

            if !response.actionsTaken.isEmpty {
                Divider()
                ForEach(response.actionsTaken, id: \.actionType) { action in
                    HStack(spacing: 6) {
                        Image(systemName: action.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundStyle(action.success ? .green : .red)
                            .font(.caption)
                        Text(action.description)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color.black.opacity(0.8))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, (int >> 16) & 0xFF, (int >> 8) & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = ((int >> 24) & 0xFF, (int >> 16) & 0xFF, (int >> 8) & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
