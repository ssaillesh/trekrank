import SwiftUI

struct RootView: View {
    @EnvironmentObject var session: SessionStore

    var body: some View {
        Group {
            if session.isAuthenticated {
                MainTabView()
            } else {
                AuthView()
            }
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            // Combined home: log trips + see them posted to the feed.
            FeedView()
                .tabItem { Label("Home", systemImage: "house") }
            LeaderboardView()
                .tabItem { Label("Ranks", systemImage: "trophy") }
            RecordView()
                .tabItem { Label("Record", systemImage: "record.circle") }
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
    }
}
