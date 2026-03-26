import Foundation
import Observation
import SwiftUI

@Observable
final class ChatViewModel {

    // MARK: - Published State

    var messages: [ChatMessage] = []
    var currentConversationId: String?
    var isStreaming: Bool = false
    var activeMode: AgentMode = .jarvis
    var inputText: String = ""
    var errorMessage: String?

    // MARK: - Private

    private var streamingMessageId: String?

    // MARK: - Init

    init() {
        messages.append(
            ChatMessage(
                role: .system,
                content: "Welcome. I am \(activeMode.displayName). How can I assist you?",
                mode: activeMode
            )
        )
    }

    // MARK: - Send Message

    func sendMessage(text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        errorMessage = nil

        // Add user message
        let userMessage = ChatMessage(role: .user, content: trimmed, mode: activeMode)
        messages.append(userMessage)

        // Clear input
        inputText = ""

        // Create placeholder assistant message for streaming
        let assistantId = UUID().uuidString
        let assistantMessage = ChatMessage(
            id: assistantId,
            role: .assistant,
            content: "",
            mode: activeMode
        )
        messages.append(assistantMessage)
        streamingMessageId = assistantId
        isStreaming = true

        do {
            let response = try await NexusAPI.shared.sendChat(
                message: trimmed,
                mode: activeMode,
                conversationId: currentConversationId
            )

            // Update streaming message with response
            if let index = messages.firstIndex(where: { $0.id == assistantId }) {
                messages[index].content = response.content
            }

            // Update conversation ID if provided
            if let conversationId = response.conversationId {
                currentConversationId = conversationId
            }
        } catch {
            // Update streaming message with error
            if let index = messages.firstIndex(where: { $0.id == assistantId }) {
                messages[index].content = "I encountered an error. Please try again."
            }
            errorMessage = error.localizedDescription
        }

        isStreaming = false
        streamingMessageId = nil
    }

    // MARK: - Switch Mode

    func switchMode(to mode: AgentMode) {
        guard mode != activeMode else { return }
        activeMode = mode

        let announcement = ChatMessage(
            role: .system,
            content: "\(mode.displayName) mode activated. \(mode.tagline)",
            mode: mode
        )
        messages.append(announcement)
    }

    // MARK: - Conversation Management

    func startNewConversation() {
        messages.removeAll()
        currentConversationId = nil
        streamingMessageId = nil
        isStreaming = false

        messages.append(
            ChatMessage(
                role: .system,
                content: "\(activeMode.displayName) is ready. \(activeMode.tagline)",
                mode: activeMode
            )
        )
    }
}

// MARK: - NexusAPI

/// Networking layer for communicating with the Nexus backend.
/// Replace the placeholder implementation with real HTTP calls.
enum NexusAPI {
    static let shared = NexusAPI.self

    struct ChatResponse {
        let content: String
        let conversationId: String?
    }

    static func sendChat(
        message: String,
        mode: AgentMode,
        conversationId: String?
    ) async throws -> ChatResponse {
        let serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000"
        let apiKey = UserDefaults.standard.string(forKey: "apiKey") ?? ""

        let url = URL(string: "\(serverURL)/api/v1/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        if !apiKey.isEmpty {
            request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "message": message,
            "mode": mode.rawValue,
            "conversation_id": conversationId as Any
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        request.timeoutInterval = 60

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }

        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let content = json?["response"] as? String ?? "No response received."
        let newConversationId = json?["conversation_id"] as? String

        return ChatResponse(content: content, conversationId: newConversationId)
    }
}
