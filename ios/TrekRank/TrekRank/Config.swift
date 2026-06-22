import Foundation

enum Config {
    /// Base URL of the TrekRank API. Use your machine's LAN IP when running on a
    /// physical device; localhost works on the iOS Simulator.
    static let apiBaseURL = URL(string: "http://127.0.0.1:8001/api/v1")!
}
