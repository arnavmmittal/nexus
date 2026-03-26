import Foundation

/// API client for the Nexus FastAPI backend.
actor NexusAPI {

    // MARK: - Singleton

    static let shared = NexusAPI()

    // MARK: - Configuration

    private static let baseURLKey = "nexus_base_url"
    private static let defaultBaseURL = "http://localhost:8000"

    var baseURL: String {
        get {
            UserDefaults.standard.string(forKey: Self.baseURLKey) ?? Self.defaultBaseURL
        }
        set {
            UserDefaults.standard.set(newValue, forKey: Self.baseURLKey)
        }
    }

    // MARK: - Private

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: config)

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Voice

    /// POST /api/shortcut/voice
    func sendVoiceQuery(text: String, context: ContextLevel = .normal) async throws -> VoiceResponse {
        let body = VoiceRequest(text: text, context: context)
        return try await post(path: "/api/shortcut/voice", body: body)
    }

    // MARK: - Chat

    /// POST /api/chat/message
    func sendChatMessage(text: String, conversationId: String? = nil) async throws -> ChatResponse {
        let body = ChatRequest(text: text, conversationId: conversationId)
        return try await post(path: "/api/chat/message", body: body)
    }

    /// POST /api/chat/message with Server-Sent Events streaming.
    /// Returns an `AsyncStream` of incremental text deltas.
    func streamChatMessage(text: String, conversationId: String? = nil) -> AsyncStream<ChatStreamChunk> {
        AsyncStream { continuation in
            Task { [weak self] in
                guard let self else {
                    continuation.finish()
                    return
                }
                do {
                    let request = try await self.buildRequest(
                        path: "/api/chat/message",
                        method: "POST",
                        body: ChatRequest(text: text, conversationId: conversationId),
                        extraHeaders: ["Accept": "text/event-stream"]
                    )
                    let (bytes, response) = try await self.session.bytes(for: request)
                    try self.validateHTTPResponse(response)

                    for try await line in bytes.lines {
                        // SSE format: "data: {json}"
                        guard line.hasPrefix("data: ") else { continue }
                        let jsonString = String(line.dropFirst(6))
                        if jsonString == "[DONE]" { break }
                        guard let data = jsonString.data(using: .utf8) else { continue }
                        if let chunk = try? self.decoder.decode(ChatStreamChunk.self, from: data) {
                            continuation.yield(chunk)
                            if chunk.done == true { break }
                        }
                    }
                } catch {
                    // Stream ended or errored — just finish.
                }
                continuation.finish()
            }
        }
    }

    // MARK: - Status

    /// GET /api/shortcut/status
    func getStatus() async throws -> StatusResponse {
        return try await get(path: "/api/shortcut/status")
    }

    // MARK: - Home Action

    /// POST /api/shortcut/home/{action}
    func homeAction(
        action: String,
        room: String? = nil,
        brightness: Int? = nil,
        temperature: Double? = nil
    ) async throws -> HomeActionResponse {
        let body = HomeActionRequest(room: room, brightness: brightness, temperature: temperature)
        return try await post(path: "/api/shortcut/home/\(action)", body: body)
    }

    // MARK: - Reminder

    /// POST /api/shortcut/remind
    func createReminder(text: String, when: String) async throws -> ReminderResponse {
        let body = ReminderRequest(text: text, when: when)
        return try await post(path: "/api/shortcut/remind", body: body)
    }

    // MARK: - Generic Helpers

    private func get<T: Decodable>(path: String) async throws -> T {
        let request = try buildRequest(path: path, method: "GET")
        return try await execute(request)
    }

    private func post<B: Encodable, T: Decodable>(path: String, body: B) async throws -> T {
        let request = try buildRequest(path: path, method: "POST", body: body)
        return try await execute(request)
    }

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw NexusAPIError.networkError(error)
        }

        try validateHTTPResponse(response)

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw NexusAPIError.decodingError(error)
        }
    }

    // MARK: - Request Building

    private func buildRequest<B: Encodable>(
        path: String,
        method: String,
        body: B? = nil as String?,
        extraHeaders: [String: String] = [:]
    ) throws -> URLRequest {
        guard let url = URL(string: baseURL + path) else {
            throw NexusAPIError.invalidURL
        }

        guard let apiKey = KeychainService.shared.apiKey, !apiKey.isEmpty else {
            throw NexusAPIError.noAPIKey
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

        for (key, value) in extraHeaders {
            request.setValue(value, forHTTPHeaderField: key)
        }

        if method != "GET", let body {
            request.httpBody = try encoder.encode(body)
        }

        return request
    }

    /// Overload for requests with no body.
    private func buildRequest(
        path: String,
        method: String,
        extraHeaders: [String: String] = [:]
    ) throws -> URLRequest {
        try buildRequest(path: path, method: method, body: nil as String?, extraHeaders: extraHeaders)
    }

    // MARK: - Response Validation

    private func validateHTTPResponse(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else { return }
        switch http.statusCode {
        case 200...299:
            return
        case 401:
            throw NexusAPIError.unauthorized
        case 403:
            throw NexusAPIError.forbidden
        case 404:
            throw NexusAPIError.notFound
        default:
            throw NexusAPIError.serverError(statusCode: http.statusCode, message: nil)
        }
    }
}
