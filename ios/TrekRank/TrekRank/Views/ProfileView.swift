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
                    if let username = session.profile?.username {
                        ProfileMapCard(username: username)
                    }
                    shareSection
                    FeaturedBadgesSection(
                        allBadges: vm.badges,
                        featuredIds: session.profile?.featuredBadges ?? [],
                        isOwner: true
                    ) { ids in
                        Task { await session.setFeaturedBadges(ids) }
                    }
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
    @Published var status: FollowStatus?
    @Published var working = false
    @Published var loading = false

    func load(_ username: String) async {
        loading = true
        profile = try? await APIClient.shared.user(username: username)
        badges = (try? await APIClient.shared.userBadges(username: username)) ?? []
        status = try? await APIClient.shared.followStatus(username: username)
        loading = false
    }

    func toggleFollow(_ username: String) async {
        guard let s = status, !s.isSelf, !working else { return }
        working = true
        do {
            if s.isFollowing { try await APIClient.shared.unfollow(username: username) }
            else { try await APIClient.shared.follow(username: username) }
            status = try? await APIClient.shared.followStatus(username: username)
        } catch { }
        working = false
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
                if let s = vm.status {
                    HStack(spacing: 22) {
                        followStat(s.followers, "Followers")
                        followStat(s.following, "Following")
                        Spacer()
                        if !s.isSelf { followButton(s) }
                    }
                }
                if let bio = vm.profile?.bio, !bio.isEmpty {
                    Text(bio).font(.subheadline)
                }
                ProfileStatsRow(profile: vm.profile)
                ProfileMapCard(username: username)
                FeaturedBadgesSection(
                    allBadges: vm.badges,
                    featuredIds: vm.profile?.featuredBadges ?? [],
                    isOwner: false
                )
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

    private func followStat(_ value: Int, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text("\(value)").font(.headline.bold())
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
    }

    private func followButton(_ s: FollowStatus) -> some View {
        Button {
            Task { await vm.toggleFollow(username) }
        } label: {
            HStack(spacing: 6) {
                if vm.working { ProgressView().controlSize(.small) }
                Label(s.isFollowing ? "Following" : "Follow",
                      systemImage: s.isFollowing ? "checkmark" : "plus")
                    .font(.subheadline.bold())
            }
            .padding(.horizontal, 18).padding(.vertical, 9)
            .background(s.isFollowing ? Color.gray.opacity(0.25) : TrekTheme.accent, in: Capsule())
            .foregroundStyle(s.isFollowing ? Color.primary : Color.black)
        }
        .disabled(vm.working)
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
/// Tapping any badge opens its detail (title + description + spin).
struct AchievementsShowcase: View {
    let badges: [Badge]
    @State private var detail: Badge?

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
                    ForEach(sorted) { badge in
                        Button { detail = badge } label: { AchievementTile(badge: badge) }
                            .buttonStyle(.plain)
                    }
                }
            }
        }
        .sheet(item: $detail) { BadgeDetailSheet(badge: $0) }
    }
}

struct AchievementTile: View {
    let badge: Badge

    var body: some View {
        VStack(spacing: 6) {
            BadgeMedallion(badge: badge, size: 46)
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

// MARK: - Featured badges (the showcase the user pins, max 3)

/// The pinned-badge showcase shown near the top of a profile. Read-only for
/// other people's profiles; the owner gets an Edit button to choose up to 3.
struct FeaturedBadgesSection: View {
    let allBadges: [Badge]          // full catalog (with earned flags)
    let featuredIds: [String]
    var isOwner: Bool
    var onSave: ([String]) -> Void = { _ in }

    @State private var detail: Badge?
    @State private var editing = false

    // Resolve ids → badges, preserving the user's chosen order.
    private var featured: [Badge] {
        featuredIds.compactMap { id in allBadges.first { $0.id == id } }
    }
    private var earned: [Badge] {
        allBadges.filter { $0.earned }.sorted { $0.name < $1.name }
    }

    var body: some View {
        // Hide entirely for visitors when nothing is pinned; owners always see it
        // so they can add badges.
        if !featured.isEmpty || isOwner {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Showcase").font(.title3.bold())
                    Spacer()
                    if isOwner {
                        Button { editing = true } label: {
                            Label(featured.isEmpty ? "Pick" : "Edit",
                                  systemImage: "slider.horizontal.3")
                                .font(.subheadline.bold())
                        }
                        .tint(TrekTheme.accent)
                    }
                }
                if featured.isEmpty {
                    Text("Pin up to 3 favorite badges to show off here.")
                        .font(.subheadline).foregroundStyle(.secondary)
                } else {
                    HStack(alignment: .top, spacing: 16) {
                        ForEach(featured) { badge in
                            VStack(spacing: 8) {
                                SpinnableBadge(badge: badge, size: 78) { detail = badge }
                                Text(badge.name)
                                    .font(.caption2.bold()).multilineTextAlignment(.center)
                                    .lineLimit(2)
                            }
                            .frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            .padding(16)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(.white.opacity(0.10), lineWidth: 1))
            .sheet(item: $detail) { BadgeDetailSheet(badge: $0) }
            .sheet(isPresented: $editing) {
                FeaturedBadgesPicker(earned: earned, initial: featuredIds) { ids in
                    onSave(ids)
                }
            }
        }
    }
}

/// A badge you can drag to spin in 3D; tap to open its details. The spin is
/// gesture-driven only (no perpetual animation), so it stays GPU-cheap.
struct SpinnableBadge: View {
    let badge: Badge
    var size: CGFloat = 78
    var onTap: () -> Void = {}

    @State private var angle: Double = 0
    @GestureState private var dragAngle: Double = 0

    var body: some View {
        BadgeMedallion(badge: badge, size: size)
            .rotation3DEffect(.degrees(angle + dragAngle),
                              axis: (x: 0, y: 1, z: 0), perspective: 0.6)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 1)
                    .updating($dragAngle) { value, state, _ in state = Double(value.translation.width) }
                    .onEnded { value in angle += Double(value.translation.width) }
            )
            .onTapGesture { onTap() }
            .animation(.spring(response: 0.45, dampingFraction: 0.75), value: dragAngle)
    }
}

/// Detail sheet for a single badge: its title, description, earned state, and a
/// large badge you can spin.
struct BadgeDetailSheet: View {
    let badge: Badge
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 16) {
            Capsule().fill(.secondary).frame(width: 36, height: 4).padding(.top, 10)
            Spacer(minLength: 4)
            SpinnableBadge(badge: badge, size: 150)
            Text(badge.name).font(.title2.bold())
            Text(badge.description)
                .font(.subheadline).foregroundStyle(.secondary)
                .multilineTextAlignment(.center).padding(.horizontal, 24)
            if badge.earned {
                Label("Earned", systemImage: "checkmark.seal.fill")
                    .font(.subheadline.bold()).foregroundStyle(TrekTheme.accent)
            } else {
                Label("Locked", systemImage: "lock.fill")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Text("Drag the badge to spin it")
                .font(.caption2).foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .background(ScreenBackground())
        .presentationDetents([.medium, .large])
    }
}

/// Lets the owner pick up to 3 earned badges (tap to toggle); the order tapped
/// is the display order, shown as a numbered chip.
struct FeaturedBadgesPicker: View {
    let earned: [Badge]
    let initial: [String]
    var onSave: ([String]) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var selected: [String]

    init(earned: [Badge], initial: [String], onSave: @escaping ([String]) -> Void) {
        self.earned = earned
        self.initial = initial
        self.onSave = onSave
        _selected = State(initialValue: initial)
    }

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 3)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("\(selected.count)/3 selected · tap to choose, tap again to remove")
                        .font(.caption).foregroundStyle(.secondary)
                    if earned.isEmpty {
                        Text("Earn some badges first, then pin your favorites here.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    } else {
                        LazyVGrid(columns: columns, spacing: 12) {
                            ForEach(earned) { badge in
                                Button { toggle(badge) } label: {
                                    pickTile(badge, rank: selected.firstIndex(of: badge.id))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .padding()
            }
            .trekScreen()
            .navigationTitle("Showcase")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { onSave(selected); dismiss() }
                }
            }
        }
    }

    private func toggle(_ badge: Badge) {
        if let i = selected.firstIndex(of: badge.id) {
            selected.remove(at: i)
        } else if selected.count < 3 {
            selected.append(badge.id)
        }
    }

    private func pickTile(_ badge: Badge, rank: Int?) -> some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topTrailing) {
                BadgeMedallion(badge: badge, size: 52)
                if let r = rank {
                    Text("\(r + 1)")
                        .font(.caption2.bold()).foregroundStyle(.black)
                        .frame(width: 18, height: 18)
                        .background(TrekTheme.accent, in: Circle())
                        .offset(x: 8, y: -6)
                }
            }
            Text(badge.name)
                .font(.caption2).multilineTextAlignment(.center).lineLimit(2)
        }
        .frame(maxWidth: .infinity).frame(height: 104).padding(8)
        .background(rank != nil ? TrekTheme.accent.opacity(0.16) : Color.gray.opacity(0.10),
                    in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14)
            .stroke(rank != nil ? TrekTheme.accent : .clear, lineWidth: 1.5))
    }
}
