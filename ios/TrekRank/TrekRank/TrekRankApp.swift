import SwiftUI

@main
struct TrekRankApp: App {
    @StateObject private var session = SessionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .tint(TrekTheme.accent)
        }
    }
}

enum TrekTheme {
    static let accent = Color(red: 0.37, green: 0.92, blue: 0.83)
    static let deep = Color(red: 0.09, green: 0.13, blue: 0.22)
}
