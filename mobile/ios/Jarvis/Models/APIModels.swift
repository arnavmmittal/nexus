import Foundation

// MARK: - Context Level

enum ContextLevel: String, Codable, CaseIterable {
    case brief
    case normal
    case detailed
}

// MARK: - Voice

struct VoiceRequest: Codable {
    let text: String
    let context: ContextLevel
}

struct VoiceResponse: Codable {
    let text: String
    let audioURL: String?
    let action: String?
    let actionResult: ActionResult?

    enum CodingKeys: String, CodingKey {
        case text
        case audioURL = "audio_url"
        case action
        case actionResult = "action_result"
    }
}

struct ActionResult: Codable {
    let success: Bool
    let message: String?
    let data: [String: AnyCodable]?
}

// MARK: - Chat

struct ChatMessage: Codable, Identifiable {
    let id: String
    let role: String
    let content: String
    let timestamp: Date?

    init(id: String = UUID().uuidString, role: String, content: String, timestamp: Date? = nil) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }
}

struct ChatRequest: Codable {
    let text: String
    let conversationId: String?

    enum CodingKeys: String, CodingKey {
        case text
        case conversationId = "conversation_id"
    }
}

struct ChatResponse: Codable {
    let message: String
    let conversationId: String
    let sources: [String]?

    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case sources
    }
}

/// Represents a single streamed chunk from the chat endpoint.
struct ChatStreamChunk: Codable {
    let delta: String?
    let conversationId: String?
    let done: Bool?

    enum CodingKeys: String, CodingKey {
        case delta
        case conversationId = "conversation_id"
        case done
    }
}

// MARK: - Status

struct StatusResponse: Codable {
    let status: String
    let version: String?
    let services: [String: ServiceStatus]?
}

struct ServiceStatus: Codable {
    let healthy: Bool
    let latency: Double?
}

// MARK: - Home Action

struct HomeActionRequest: Codable {
    let room: String?
    let brightness: Int?
    let temperature: Double?
}

struct HomeActionResponse: Codable {
    let success: Bool
    let message: String
    let device: String?
    let state: [String: AnyCodable]?
}

// MARK: - Reminder

struct ReminderRequest: Codable {
    let text: String
    let when: String

    enum CodingKeys: String, CodingKey {
        case text
        case when = "when"
    }
}

struct ReminderResponse: Codable {
    let success: Bool
    let reminderId: String?
    let scheduledFor: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case success
        case reminderId = "reminder_id"
        case scheduledFor = "scheduled_for"
        case message
    }
}

// MARK: - API Error

enum NexusAPIError: Error, LocalizedError {
    case invalidURL
    case unauthorized
    case forbidden
    case notFound
    case serverError(statusCode: Int, message: String?)
    case decodingError(Error)
    case networkError(Error)
    case noAPIKey
    case streamingError(String)
    case unknown(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL configuration."
        case .unauthorized:
            return "Invalid or missing API key."
        case .forbidden:
            return "Access denied."
        case .notFound:
            return "Requested resource not found."
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message ?? "Unknown")"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .noAPIKey:
            return "No API key configured. Add one in Settings."
        case .streamingError(let detail):
            return "Streaming error: \(detail)"
        case .unknown(let detail):
            return detail
        }
    }
}

// MARK: - AnyCodable Helper

/// A type-erased Codable value for dynamic JSON fields.
struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            value = NSNull()
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map(\.value)
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues(\.value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported type")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case is NSNull:
            try container.encodeNil()
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        default:
            throw EncodingError.invalidValue(value, .init(codingPath: encoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
}
