import WidgetKit
import SwiftUI

// MARK: - Widget Bundle

@main
struct JarvisWidgetBundle: WidgetBundle {
    var body: some Widget {
        QuickActionsWidget()
        StatusWidget()
    }
}

// MARK: - Quick Actions Widget

/// Home screen widget with quick action buttons for Jarvis.
struct QuickActionsWidget: Widget {
    let kind = "QuickActionsWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: QuickActionsProvider()) { entry in
            QuickActionsWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Jarvis Quick Actions")
        .description("Quick access to Jarvis commands")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct QuickActionsEntry: TimelineEntry {
    let date: Date
    let greeting: String
}

struct QuickActionsProvider: TimelineProvider {
    func placeholder(in context: Context) -> QuickActionsEntry {
        QuickActionsEntry(date: .now, greeting: "Hey there")
    }

    func getSnapshot(in context: Context, completion: @escaping (QuickActionsEntry) -> Void) {
        completion(QuickActionsEntry(date: .now, greeting: timeGreeting()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<QuickActionsEntry>) -> Void) {
        let entry = QuickActionsEntry(date: .now, greeting: timeGreeting())
        // Refresh every 30 minutes for updated greeting
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: .now)!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func timeGreeting() -> String {
        let hour = Calendar.current.component(.hour, from: .now)
        if hour < 12 { return "Good morning" }
        if hour < 17 { return "Good afternoon" }
        return "Good evening"
    }
}

struct QuickActionsWidgetView: View {
    let entry: QuickActionsEntry

    @Environment(\.widgetFamily) var family

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Circle()
                    .fill(Color(hex: "10b981"))
                    .frame(width: 10, height: 10)
                Text("Jarvis")
                    .font(.caption.bold())
                    .foregroundStyle(Color(hex: "10b981"))
            }

            Text(entry.greeting)
                .font(.headline)
                .foregroundStyle(.white)

            if family == .systemMedium {
                // Medium widget: show action buttons
                HStack(spacing: 12) {
                    WidgetActionLink(icon: "mic.fill", label: "Talk", url: "nexus-jarvis://voice")
                    WidgetActionLink(icon: "lightbulb.fill", label: "Lights", url: "nexus-jarvis://home/lights")
                    WidgetActionLink(icon: "bell.fill", label: "Remind", url: "nexus-jarvis://remind")
                    WidgetActionLink(icon: "house.fill", label: "Status", url: "nexus-jarvis://status")
                }
            } else {
                // Small widget: just open voice
                Spacer()
                HStack {
                    Spacer()
                    Image(systemName: "mic.fill")
                        .font(.title2)
                        .foregroundStyle(Color(hex: "10b981"))
                    Spacer()
                }
                Text("Tap to talk")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
            }
        }
        .widgetURL(URL(string: "nexus-jarvis://voice"))
    }
}

struct WidgetActionLink: View {
    let icon: String
    let label: String
    let url: String

    var body: some View {
        Link(destination: URL(string: url)!) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.body)
                    .foregroundStyle(Color(hex: "10b981"))
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Status Widget

/// Shows current status: time, next event, home status.
struct StatusWidget: Widget {
    let kind = "StatusWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: StatusProvider()) { entry in
            StatusWidgetView(entry: entry)
                .containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Jarvis Status")
        .description("Current status and next event")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular])
    }
}

struct StatusEntry: TimelineEntry {
    let date: Date
    let greeting: String
    let nextEvent: String?
    let temperature: String?
    let lightsOn: Int?
}

struct StatusProvider: TimelineProvider {
    func placeholder(in context: Context) -> StatusEntry {
        StatusEntry(date: .now, greeting: "Good morning", nextEvent: "Team standup at 9 AM", temperature: "72", lightsOn: 3)
    }

    func getSnapshot(in context: Context, completion: @escaping (StatusEntry) -> Void) {
        completion(StatusEntry(date: .now, greeting: timeGreeting(), nextEvent: nil, temperature: nil, lightsOn: nil))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<StatusEntry>) -> Void) {
        // TODO: Fetch real data from Nexus API via background task
        let entry = StatusEntry(
            date: .now,
            greeting: timeGreeting(),
            nextEvent: nil,
            temperature: nil,
            lightsOn: nil
        )
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: .now)!
        completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
    }

    private func timeGreeting() -> String {
        let hour = Calendar.current.component(.hour, from: .now)
        if hour < 12 { return "Good morning" }
        if hour < 17 { return "Good afternoon" }
        return "Good evening"
    }
}

struct StatusWidgetView: View {
    let entry: StatusEntry

    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .accessoryCircular:
            // Lock screen circular complication
            ZStack {
                AccessoryWidgetBackground()
                Image(systemName: "brain.head.profile")
                    .font(.title2)
            }
        case .accessoryRectangular:
            // Lock screen rectangular complication
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Image(systemName: "brain.head.profile")
                        .font(.caption2)
                    Text("Jarvis")
                        .font(.caption2.bold())
                }
                if let event = entry.nextEvent {
                    Text(event)
                        .font(.caption)
                }
                Text(entry.date, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        default:
            // Home screen widget
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Circle()
                        .fill(Color(hex: "10b981"))
                        .frame(width: 8, height: 8)
                    Text(entry.date, style: .time)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Text(entry.greeting)
                    .font(.headline)
                    .foregroundStyle(.white)

                if let event = entry.nextEvent {
                    HStack(spacing: 4) {
                        Image(systemName: "calendar")
                            .font(.caption2)
                            .foregroundStyle(Color(hex: "3b82f6"))
                        Text(event)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if family == .systemMedium {
                    HStack(spacing: 16) {
                        if let temp = entry.temperature {
                            Label(temp + "F", systemImage: "thermometer.medium")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        if let lights = entry.lightsOn {
                            Label("\(lights) lights on", systemImage: "lightbulb.fill")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Spacer()
            }
            .widgetURL(URL(string: "nexus-jarvis://dashboard"))
        }
    }
}

// MARK: - Color Extension

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
