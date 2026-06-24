import SwiftUI

@main
struct TrekRankApp: App {
    @StateObject private var session = SessionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .tint(TrekTheme.accent)
                .preferredColorScheme(.dark)
        }
    }
}
