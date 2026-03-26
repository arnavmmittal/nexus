import Foundation
import CoreLocation

// MARK: - Vehicle API Models

struct VehicleStatePayload: Codable {
    let isDriving: Bool
    let location: [Double]?
    let destination: String?
    let etaMinutes: Int?
    let speedMph: Double?

    enum CodingKeys: String, CodingKey {
        case isDriving = "is_driving"
        case location
        case destination
        case etaMinutes = "eta_minutes"
        case speedMph = "speed_mph"
    }
}

struct VehicleStateResponse: Codable {
    let isDriving: Bool
    let location: [Double]?
    let destination: String?
    let etaMinutes: Int?
    let speedMph: Double?
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case isDriving = "is_driving"
        case location
        case destination
        case etaMinutes = "eta_minutes"
        case speedMph = "speed_mph"
        case updatedAt = "updated_at"
    }
}

struct CommuteBriefingResponse: Codable {
    let summary: String
    let weather: String?
    let calendarEvents: [String]
    let reminders: [String]
    let trafficNotes: String?
    let estimatedArrival: String?

    enum CodingKeys: String, CodingKey {
        case summary
        case weather
        case calendarEvents = "calendar_events"
        case reminders
        case trafficNotes = "traffic_notes"
        case estimatedArrival = "estimated_arrival"
    }
}

struct OnMyWayHomeRequest: Codable {
    let memberId: String

    enum CodingKeys: String, CodingKey {
        case memberId = "member_id"
    }
}

struct OnMyWayHomeResponse: Codable {
    let status: String
    let presence: String
    let destination: String
    let hooksFired: Int
    let hookResults: [String]

    enum CodingKeys: String, CodingKey {
        case status
        case presence
        case destination
        case hooksFired = "hooks_fired"
        case hookResults = "hook_results"
    }
}

// MARK: - Vehicle Service

/// Manages driving mode, location tracking, and communication with the Nexus vehicle API.
actor VehicleService: NSObject {

    // MARK: - Singleton

    static let shared = VehicleService()

    // MARK: - State

    private(set) var isDriving = false
    private(set) var latestBriefing: CommuteBriefingResponse?
    private(set) var latestState: VehicleStateResponse?

    // MARK: - Private

    private var locationManager: CLLocationManager?
    private var locationDelegate: LocationDelegate?
    private var updateTimer: Timer?
    private let updateInterval: TimeInterval = 15  // seconds between state pushes

    private let api = NexusAPI.shared

    // MARK: - Driving Mode Control

    /// Start driving mode — begins location tracking and periodic state uploads.
    func startDrivingMode() async {
        guard !isDriving else { return }
        isDriving = true

        await MainActor.run { [weak self] in
            guard let self else { return }
            let manager = CLLocationManager()
            let delegate = LocationDelegate { [weak self] location in
                Task { [weak self] in
                    await self?.handleLocationUpdate(location)
                }
            }
            manager.delegate = delegate
            manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
            manager.allowsBackgroundLocationUpdates = true
            manager.pausesLocationUpdatesAutomatically = false
            manager.requestWhenInUseAuthorization()
            manager.startUpdatingLocation()

            // Hold references so they don't deallocate
            Task { [weak self] in
                await self?.storeLocationManager(manager, delegate: delegate)
            }
        }

        // Push initial state
        await pushState(location: nil)
    }

    /// Stop driving mode — stops location tracking.
    func stopDrivingMode() async {
        guard isDriving else { return }
        isDriving = false

        await MainActor.run { [weak self] in
            Task { [weak self] in
                let manager = await self?.locationManager
                manager?.stopUpdatingLocation()
            }
        }

        locationManager = nil
        locationDelegate = nil

        // Push final "not driving" state
        await pushState(location: nil)
    }

    // MARK: - API Calls

    /// Generate a commute briefing from the backend.
    func generateBriefing(destination: String? = nil) async throws -> CommuteBriefingResponse {
        var path = "/api/vehicle/briefing"
        if let dest = destination {
            path += "?destination=\(dest.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? dest)"
        }
        let briefing: CommuteBriefingResponse = try await api.get(path: path)
        latestBriefing = briefing
        return briefing
    }

    /// Trigger the "On My Way Home" automation.
    func onMyWayHome(memberId: String = "primary") async throws -> OnMyWayHomeResponse {
        let body = OnMyWayHomeRequest(memberId: memberId)
        let response: OnMyWayHomeResponse = try await api.post(
            path: "/api/vehicle/on-my-way-home",
            body: body
        )
        return response
    }

    /// Fetch the current vehicle state from the backend.
    func fetchState() async throws -> VehicleStateResponse {
        let state: VehicleStateResponse = try await api.get(path: "/api/vehicle/state")
        latestState = state
        return state
    }

    // MARK: - Private Helpers

    private func storeLocationManager(_ manager: CLLocationManager, delegate: LocationDelegate) {
        self.locationManager = manager
        self.locationDelegate = delegate
    }

    private func handleLocationUpdate(_ location: CLLocation) async {
        guard isDriving else { return }
        await pushState(location: location)
    }

    private func pushState(location: CLLocation?) async {
        let loc: [Double]? = location.map { [$0.coordinate.latitude, $0.coordinate.longitude] }
        let speed: Double? = location.map { max(0, $0.speed * 2.23694) }  // m/s to mph

        let payload = VehicleStatePayload(
            isDriving: isDriving,
            location: loc,
            destination: latestState?.destination,
            etaMinutes: latestState?.etaMinutes,
            speedMph: speed
        )

        do {
            let response: VehicleStateResponse = try await api.post(
                path: "/api/vehicle/state",
                body: payload
            )
            latestState = response
        } catch {
            // Silently handle — driving mode should not crash on a failed upload.
        }
    }
}

// MARK: - Location Delegate

/// Bridges CLLocationManager delegate callbacks into an async-friendly closure.
private final class LocationDelegate: NSObject, CLLocationManagerDelegate {
    private let onUpdate: (CLLocation) -> Void

    init(onUpdate: @escaping (CLLocation) -> Void) {
        self.onUpdate = onUpdate
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let latest = locations.last else { return }
        onUpdate(latest)
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.startUpdatingLocation()
        default:
            break
        }
    }
}

