import SwiftUI

@MainActor
final class ProfileViewModel: ObservableObject {
    @Published var badges: [Badge] = []
    @Published var shareURL: URL?
    @Published var generatingCard = false

    func load() async {
        badges = (try? await APIClient.shared.badges()) ?? []
    }

    func makeShareCard() async {
        generatingCard = true
        if let resp = try? await APIClient.shared.shareCard(year: Calendar.current.component(.year, from: Date())) {
            shareURL = URL(string: resp.imageUrl)
        }
        generatingCard = false
    }
}

/// The signed-in user's own profile (social-media layout) + settings/share.
struct ProfileView: View {
    @EnvironmentObject var session: SessionStore
    @StateObject private var vm = ProfileViewModel()
    @State private var showSettings = false
    @AppStorage(Units.storageKey) private var useMiles = false  // re-render on unit change

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    ProfileHero(profile: session.profile)
                    if let bio = session.profile?.bio, !bio.isEmpty {
                        Text(bio).font(.subheadline)
                    }
                    ProfileStatsRow(profile: session.profile)
                    shareSection
                    AchievementsShowcase(badges: vm.badges)
                }
                .padding()
            }
            .trekScreen()
            .navigationTitle("Profile")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: {
                        Image(systemName: "gearshape.fill").foregroundStyle(TrekTheme.accent)
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView().environmentObject(session)
            }
            .task { await session.refreshProfile(); await vm.load() }
        }
    }

    private var shareSection: some View {
        VStack(spacing: 10) {
            Button {
                Task { await vm.makeShareCard() }
            } label: {
                HStack {
                    if vm.generatingCard { ProgressView().tint(.black) }
                    Label("Generate share card", systemImage: "square.and.arrow.up")
                }
            }
            .buttonStyle(NeonButtonStyle())
            if let url = vm.shareURL {
                AsyncImage(url: url) { img in
                    img.resizable().scaledToFit().clipShape(RoundedRectangle(cornerRadius: 16))
                } placeholder: { ProgressView() }
                .frame(maxHeight: 360)
            }
        }
    }
}

// MARK: - Public profile (another user)

@MainActor
final class PublicProfileViewModel: ObservableObject {
    @Published var profile: UserProfile?
    @Published var badges: [Badge] = []
    @Published var loading = false

    func load(_ username: String) async {
        loading = true
        profile = try? await APIClient.shared.user(username: username)
        badges = (try? await APIClient.shared.userBadges(username: username)) ?? []
        loading = false
    }
}

/// A read-only profile for any user — what others see: stats + badge showcase.
/// Pushed inside an existing NavigationStack, so it has none of its own.
struct PublicProfileView: View {
    let username: String
    @StateObject private var vm = PublicProfileViewModel()
    @AppStorage(Units.storageKey) private var useMiles = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                ProfileHero(profile: vm.profile)
                if let bio = vm.profile?.bio, !bio.isEmpty {
                    Text(bio).font(.subheadline)
                }
                ProfileStatsRow(profile: vm.profile)
                AchievementsShowcase(badges: vm.badges)
            }
            .padding()
        }
        .trekScreen()
        .navigationTitle("@\(username)")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if vm.loading && vm.profile == nil { ProgressView().tint(TrekTheme.accent) } }
        .task { await vm.load(username) }
    }
}

// MARK: - Shared building blocks

/// Avatar + name + handle + home location.
struct ProfileHero: View {
    let profile: UserProfile?

    var body: some View {
        HStack(spacing: 16) {
            Circle()
                .fill(LinearGradient(colors: [TrekTheme.accent, TrekTheme.accent2],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: 78, height: 78)
                .overlay(Text(String((profile?.username ?? "?").prefix(1)).uppercased())
                    .font(.largeTitle.bold()).foregroundStyle(.black))
                .shadow(color: TrekTheme.accent.opacity(0.5), radius: 14)
            VStack(alignment: .leading, spacing: 4) {
                Text(profile?.displayName ?? " ").font(.title2.bold())
                Text("@\(profile?.username ?? "")").foregroundStyle(.secondary)
                if let city = profile?.homeCity, !city.isEmpty {
                    Label(city + (profile?.homeCountry.map { ", \($0)" } ?? ""),
                          systemImage: "mappin.and.ellipse")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
    }
}

/// Instagram-style horizontal stats strip.
struct ProfileStatsRow: View {
    let profile: UserProfile?

    var body: some View {
        GlassCard {
            HStack {
                StatColumn(value: Double(profile?.totalTrips ?? 0), label: "Trips")
                Divider().frame(height: 34)
                StatColumn(value: Double(profile?.totalCountries ?? 0), label: "Countries")
                Divider().frame(height: 34)
                StatColumn(value: Double(profile?.totalCities ?? 0), label: "Cities")
                Divider().frame(height: 34)
                StatColumn(value: Units.value(km: profile?.totalKm ?? 0),
                           suffix: Units.suffix, label: "Distance")
            }
        }
    }
}

struct StatColumn: View {
    let value: Double
    var suffix: String = ""
    let label: String
    var body: some View {
        VStack(spacing: 3) {
            CountUpText(value: value, suffix: suffix)
                .font(.title3.bold()).foregroundStyle(TrekTheme.accent)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

/// Grid of achievement tiles — earned ones highlighted, locked ones muted.
struct AchievementsShowcase: View {
    let badges: [Badge]

    private var earnedCount: Int { badges.filter { $0.earned }.count }
    private let columns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 3)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Achievements").font(.title3.bold())
                Spacer()
                Text("\(earnedCount)/\(badges.count)")
                    .font(.subheadline.bold()).foregroundStyle(TrekTheme.accent)
            }
            if badges.isEmpty {
                Text("No achievements yet.").font(.subheadline).foregroundStyle(.secondary)
            } else {
                // Earned badges first, then locked, each alphabetical.
                let sorted = badges.sorted {
                    ($0.earned ? 0 : 1, $0.name) < ($1.earned ? 0 : 1, $1.name)
                }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(sorted) { AchievementTile(badge: $0) }
                }
            }
        }
    }
}

struct AchievementTile: View {
    let badge: Badge

    var body: some View {
        VStack(spacing: 6) {
            Text(badge.emoji ?? "🏅")
                .font(.system(size: 34))
                .grayscale(badge.earned ? 0 : 1)
                .opacity(badge.earned ? 1 : 0.45)
            Text(badge.name)
                .font(.caption2).multilineTextAlignment(.center).lineLimit(2)
                .foregroundStyle(badge.earned ? .primary : .secondary)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 96)
        .padding(8)
        .background(badge.earned ? TrekTheme.accent.opacity(0.12) : Color.gray.opacity(0.10),
                    in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14)
            .stroke(badge.earned ? TrekTheme.accent.opacity(0.4) : .clear, lineWidth: 1))
    }
}
