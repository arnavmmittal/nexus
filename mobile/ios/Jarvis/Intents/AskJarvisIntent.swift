import AppIntents
import Foundation

/// Siri Shortcut: "Hey Siri, ask Jarvis..."
/// Allows voice queries to Jarvis from anywhere via Siri.
struct AskJarvisIntent: AppIntent {
    static var title: LocalizedStringResource = "Ask Jarvis"
    static var description = IntentDescription("Ask your AI assistant a question")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Question")
    var query: String

    @Parameter(title: "Response Detail", default: .brief)
    var context: ContextLevel

    static var parameterSummary: some ParameterSummary {
        Summary("Ask Jarvis \(\.$query)") {
            \.$context
        }
    }

    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        let api = NexusAPI.shared
        let response = try await api.sendVoiceQuery(text: query, context: context)

        return .result(
            dialog: IntentDialog(stringLiteral: response.speech)
        ) {
            JarvisResponseSnippet(response: response)
        }
    }
}

/// Context level for Siri responses
enum ContextLevel: String, AppEnum {
    case brief
    case normal
    case detailed

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Detail Level")
    static var caseDisplayRepresentations: [ContextLevel: DisplayRepresentation] = [
        .brief: "Brief",
        .normal: "Normal",
        .detailed: "Detailed",
    ]
}

/// Shortcut: Quick home action via Siri
struct HomeActionIntent: AppIntent {
    static var title: LocalizedStringResource = "Jarvis Home Control"
    static var description = IntentDescription("Control your smart home via Jarvis")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action")
    var action: HomeAction

    @Parameter(title: "Room", default: nil)
    var room: String?

    static var parameterSummary: some ParameterSummary {
        Summary("Jarvis \(\.$action)") {
            \.$room
        }
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = NexusAPI.shared
        let response = try await api.homeAction(
            action: action.apiAction,
            room: room,
            brightness: nil,
            temperature: nil
        )

        return .result(dialog: IntentDialog(stringLiteral: response.speech))
    }
}

enum HomeAction: String, AppEnum {
    case lightsOn = "lights_on"
    case lightsOff = "lights_off"
    case status = "status"

    var apiAction: String { rawValue }

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Home Action")
    static var caseDisplayRepresentations: [HomeAction: DisplayRepresentation] = [
        .lightsOn: "Turn Lights On",
        .lightsOff: "Turn Lights Off",
        .status: "Home Status",
    ]
}

/// Shortcut: Set a reminder
struct RemindMeIntent: AppIntent {
    static var title: LocalizedStringResource = "Jarvis Remind Me"
    static var description = IntentDescription("Set a reminder via Jarvis")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "What to remember")
    var text: String

    @Parameter(title: "When")
    var when: String

    static var parameterSummary: some ParameterSummary {
        Summary("Remind me to \(\.$text) \(\.$when)")
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = NexusAPI.shared
        let response = try await api.createReminder(text: text, when: when)

        return .result(dialog: IntentDialog(stringLiteral: response.speech))
    }
}

/// App Shortcuts provider - makes intents discoverable in Shortcuts app
struct JarvisShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskJarvisIntent(),
            phrases: [
                "Ask \(.applicationName) \(\.$query)",
                "Hey \(.applicationName) \(\.$query)",
                "Tell \(.applicationName) \(\.$query)",
            ],
            shortTitle: "Ask Jarvis",
            systemImageName: "brain.head.profile"
        )

        AppShortcut(
            intent: HomeActionIntent(),
            phrases: [
                "\(.applicationName) \(\.$action)",
                "\(.applicationName) lights",
            ],
            shortTitle: "Home Control",
            systemImageName: "house.fill"
        )

        AppShortcut(
            intent: RemindMeIntent(),
            phrases: [
                "\(.applicationName) remind me \(\.$text)",
                "\(.applicationName) reminder \(\.$text)",
            ],
            shortTitle: "Remind Me",
            systemImageName: "bell.fill"
        )
    }
}
