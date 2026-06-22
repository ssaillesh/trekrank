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
            FeedView()
                .tabItem { Label("Feed", systemImage: "list.bullet.rectangle") }
            LeaderboardView()
                .tabItem { Label("Ranks", systemImage: "trophy") }
            TripsView()
                .tabItem { Label("Trips", systemImage: "airplane") }
            MapView()
                .tabItem { Label("Map", systemImage: "globe") }
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
    }
}
