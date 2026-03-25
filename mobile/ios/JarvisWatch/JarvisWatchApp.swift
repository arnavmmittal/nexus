import SwiftUI

/// Apple Watch companion app for Jarvis.
/// Provides raise-to-speak, quick replies, and complications.
@main
struct JarvisWatchApp: App {
    var body: some Scene {
        WindowGroup {
            WatchHomeView()
        }
    }
}
