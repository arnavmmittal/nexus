import Foundation
import WatchConnectivity

enum WatchVoiceState {
    case idle, listening, thinking, speaking
}

/// ViewModel for the Watch app.
/// Communicates with the iPhone app via WatchConnectivity,
/// or directly with the Nexus API if iPhone is unreachable.
@Observable
final class WatchViewModel {
    var voiceState: WatchVoiceState = .idle
    var audioLevel: Float = 0
    var displayText: String = ""
    var lastResponse: String = ""

    private let session = WCSession.default
    private var wcDelegate: WCSessionDelegateHandler?

    init() {
        setupWatchConnectivity()
    }

    // MARK: - Watch Connectivity

    private func setupWatchConnectivity() {
        guard WCSession.isSupported() else { return }
        wcDelegate = WCSessionDelegateHandler { [weak self] message in
            self?.handlePhoneMessage(message)
        }
        session.delegate = wcDelegate
        session.activate()
    }

    private func handlePhoneMessage(_ message: [String: Any]) {
        if let response = message["response"] as? String {
            displayText = response
            voiceState = .speaking

            // Reset after display
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(5))
                if voiceState == .speaking {
                    voiceState = .idle
                }
            }
        }
    }

    // MARK: - Voice Control

    func toggleListening() async {
        switch voiceState {
        case .idle:
            await startListening()
        case .listening:
            await stopListening()
        default:
            break
        }
    }

    @MainActor
    private func startListening() async {
        voiceState = .listening
        displayText = "Listening..."

        // On Watch, we use dictation as the primary input
        // The actual speech recognition happens via WatchConnectivity
        // or direct API call
    }

    @MainActor
    private func stopListening() async {
        voiceState = .thinking
        displayText = "Thinking..."

        // If we have transcribed text, send to API
        if !displayText.isEmpty && displayText != "Listening..." {
            await sendQuery(displayText)
        } else {
            voiceState = .idle
            displayText = ""
        }
    }

    // MARK: - API Communication

    @MainActor
    func sendQuery(_ text: String) async {
        voiceState = .thinking
        displayText = "Thinking..."

        // Try via WatchConnectivity first (uses iPhone's connection)
        if session.isReachable {
            session.sendMessage(
                ["action": "query", "text": text],
                replyHandler: { [weak self] reply in
                    Task { @MainActor in
                        if let response = reply["response"] as? String {
                            self?.displayText = response
                            self?.voiceState = .speaking
                        }
                    }
                },
                errorHandler: { [weak self] _ in
                    Task { @MainActor in
                        await self?.sendDirectQuery(text)
                    }
                }
            )
        } else {
            await sendDirectQuery(text)
        }
    }

    @MainActor
    private func sendDirectQuery(_ text: String) async {
        // Direct API call from Watch
        guard let url = URL(string: "\(serverURL)/api/shortcut/voice") else {
            displayText = "Configuration error"
            voiceState = .idle
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

        let body = ["text": text, "context": "brief", "voice_response": false] as [String: Any]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let speech = json["speech"] as? String {
                displayText = speech
                voiceState = .speaking

                try? await Task.sleep(for: .seconds(5))
                voiceState = .idle
            }
        } catch {
            displayText = "Connection error"
            voiceState = .idle
        }
    }

    // MARK: - Quick Actions

    @MainActor
    func quickAction(_ action: String) async {
        voiceState = .thinking

        switch action {
        case "remind":
            displayText = "Use dictation to set a reminder"
            voiceState = .idle
        default:
            await sendQuery("Run quick action: \(action)")
        }
    }

    // MARK: - Configuration

    private var serverURL: String {
        UserDefaults.standard.string(forKey: "nexus_server_url") ?? "http://localhost:8000"
    }

    private var apiKey: String {
        UserDefaults.standard.string(forKey: "nexus_api_key") ?? ""
    }
}

// MARK: - WCSession Delegate

final class WCSessionDelegateHandler: NSObject, WCSessionDelegate {
    let onMessage: ([String: Any]) -> Void

    init(onMessage: @escaping ([String: Any]) -> Void) {
        self.onMessage = onMessage
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}

    func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        onMessage(message)
    }

    func session(_ session: WCSession, didReceiveMessage message: [String: Any], replyHandler: @escaping ([String: Any]) -> Void) {
        onMessage(message)
        replyHandler(["status": "received"])
    }
}
