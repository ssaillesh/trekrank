import SwiftUI

enum FeedScope: String, CaseIterable { case posts = "Posts", people = "People" }

@MainActor
final class FeedViewModel: ObservableObject {
    @Published var items: [FeedItem] = []
    @Published var loading = false
    @Published var error: String?

    // People search
    @Published var people: [LeaderboardUser] = []
    @Published var searching = false
    @Published var requested: Set<String> = []   // usernames a request was sent to

    // Achievement celebration (a trip just unlocked one or more badges)
    @Published var celebration: Celebration?

    private var searchTask: Task<Void, Never>?
    /// Earned badge IDs as of the last sync; nil until the first sync so we
    /// don't "celebrate" the badges the user already had on launch.
    private var knownEarnedIDs: Set<String>?

    func load() async {
        loading = true; error = nil
        do { items = try await APIClient.shared.feed().items }
        catch { self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription }
        loading = false
        await syncBadges()
    }

    /// Called after the user logs a trip from the feed: show the new post right
    /// away, then keep refreshing while the server geocodes it (distance + any
    /// badges land within a couple seconds), surfacing an achievement popup.
    func refreshAfterAdd() async {
        await load()
        for _ in 0..<15 {
            try? await Task.sleep(nanoseconds: 1_200_000_000)
            let processing = ((try? await APIClient.shared.trips())?.items ?? [])
                .contains { $0.status == "processing" }
            await load()
            if !processing { break }
        }
    }

    /// If any newly-earned badge appeared since the last sync, queue a
    /// celebration. The first call only establishes a baseline.
    private func syncBadges() async {
        guard let badges = try? await APIClient.shared.badges() else { return }
        let earned = Set(badges.filter { $0.earned }.map { $0.id })
        if let known = knownEarnedIDs {
            let newIDs = earned.subtracting(known)
            if !newIDs.isEmpty {
                celebration = Celebration(badges: badges.filter { newIDs.contains($0.id) })
            }
        }
        knownEarnedIDs = earned
    }

    /// Client-side filter of loaded posts by username / city / country.
    func filteredItems(_ query: String) -> [FeedItem] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return items }
        return items.filter { item in
            if item.user.username.lowercased().contains(q) { return true }
            if let t = item.trip,
               "\(t.destCity) \(t.destCountry)".lowercased().contains(q) { return true }
            return false
        }
    }

    /// Debounced people search against the backend.
    func searchPeople(_ query: String) {
        searchTask?.cancel()
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 1 else { people = []; return }
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            searching = true
            let results = (try? await APIClient.shared.searchUsers(q)) ?? []
            if !Task.isCancelled { people = results }
            searching = false
        }
    }

    func addFriend(_ username: String) async {
        do {
            try await APIClient.shared.sendFriendRequest(username: username)
            requested.insert(username)
        } catch {
            self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription
        }
    }
}

struct FeedView: View {
    @StateObject private var vm = FeedViewModel()
    @State private var query = ""
    @State private var scope: FeedScope = .posts
    @State private var showAdd = false
    @State private var showMyTrips = false
    @State private var showRecommend = false

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 14) {
                    if scope == .people {
                        peopleResults
                    } else {
                        postsResults
                    }
                }
                .padding(.horizontal).padding(.top, 8)
            }
            .trekScreen()
            .navigationTitle("Home")
            .navigationDestination(for: String.self) { PublicProfileView(username: $0) }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showMyTrips = true } label: {
                        Image(systemName: "airplane").foregroundStyle(TrekTheme.accent)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button { showAdd = true } label: { Label("Log a trip", systemImage: "airplane") }
                        Button { showRecommend = true } label: { Label("Recommend a spot", systemImage: "lightbulb") }
                    } label: {
                        Image(systemName: "plus.circle.fill").font(.title2)
                            .foregroundStyle(TrekTheme.accent)
                    }
                }
            }
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always),
                        prompt: scope == .people ? "Search people to add" : "Search posts")
            .searchScopes($scope) {
                ForEach(FeedScope.allCases, id: \.self) { Text($0.rawValue).tag($0) }
            }
            .onChange(of: query) { _, new in
                if scope == .people { vm.searchPeople(new) }
            }
            .onChange(of: scope) { _, new in
                if new == .people { vm.searchPeople(query) }
            }
            .sheet(isPresented: $showAdd) {
                AddTripView { await vm.refreshAfterAdd() }
            }
            .sheet(isPresented: $showMyTrips) {
                MyTripsView()
            }
            .sheet(isPresented: $showRecommend) {
                RecommendComposeView { await vm.load() }
            }
            .sheet(item: $vm.celebration) { celebration in
                AchievementView(badges: celebration.badges) {
                    vm.celebration = nil   // already on the feed; just reveal it
                } onDismiss: {
                    vm.celebration = nil
                }
                .presentationDetents([.height(440)])
            }
            .refreshable { await vm.load() }
            .overlay { if vm.loading && vm.items.isEmpty && scope == .posts { ProgressView().tint(TrekTheme.accent) } }
            .task { await vm.load() }
        }
    }

    @ViewBuilder private var postsResults: some View {
        let items = vm.filteredItems(query)
        if items.isEmpty && !vm.loading {
            ContentUnavailableView(
                query.isEmpty ? "No activity yet" : "No matching posts",
                systemImage: "sparkles",
                description: Text(query.isEmpty
                    ? "Add friends and log trips to see your feed light up."
                    : "Try a different city, country, or username."))
                .padding(.top, 80)
        }
        ForEach(Array(items.enumerated()), id: \.element.id) { idx, item in
            NavigationLink(value: item.user.username) {
                FeedRow(item: item)
            }
            .buttonStyle(.plain)
            .transition(.move(edge: .bottom).combined(with: .opacity))
            .animation(.spring(response: 0.5, dampingFraction: 0.8)
                .delay(Double(min(idx, 8)) * 0.04), value: items.count)
        }
    }

    @ViewBuilder private var peopleResults: some View {
        if vm.searching {
            ProgressView().tint(TrekTheme.accent).padding(.top, 40)
        } else if query.isEmpty {
            ContentUnavailableView("Find friends", systemImage: "person.2",
                description: Text("Search by username to send a friend request."))
                .padding(.top, 80)
        } else if vm.people.isEmpty {
            ContentUnavailableView.search(text: query).padding(.top, 60)
        } else {
            ForEach(vm.people, id: \.id) { person in
                NavigationLink(value: person.username) {
                    PersonRow(person: person,
                              requested: vm.requested.contains(person.username)) {
                        Task { await vm.addFriend(person.username) }
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }
}

struct PersonRow: View {
    let person: LeaderboardUser
    let requested: Bool
    let onAdd: () -> Void

    var body: some View {
        GlassCard {
            HStack(spacing: 12) {
                Circle().fill(TrekTheme.accent.opacity(0.25)).frame(width: 40, height: 40)
                    .overlay(Text(String(person.username.prefix(1)).uppercased()).bold())
                VStack(alignment: .leading, spacing: 2) {
                    Text(person.displayName).font(.subheadline.bold())
                    Text("@\(person.username)").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button(action: onAdd) {
                    Label(requested ? "Requested" : "Add",
                          systemImage: requested ? "checkmark" : "person.badge.plus")
                        .font(.caption.bold())
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .background(requested ? Color.gray.opacity(0.25) : TrekTheme.accent,
                                    in: Capsule())
                        .foregroundStyle(requested ? Color.secondary : Color.black)
                }
                .disabled(requested)
            }
        }
    }
}

struct FeedRow: View {
    let item: FeedItem

    var body: some View {
        GlassCard {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: icon).font(.title2)
                    .foregroundStyle(TrekTheme.accent).frame(width: 38, height: 38)
                    .background(TrekTheme.accent.opacity(0.12), in: Circle())
                VStack(alignment: .leading, spacing: 4) {
                    Text("@\(item.user.username)").font(.subheadline.bold())
                    Text(detail).font(.subheadline)
                        .foregroundStyle(item.recommendation == nil ? .secondary : .primary)
                    if let place = recommendationPlace {
                        Label(place, systemImage: "mappin.and.ellipse")
                            .font(.caption2).foregroundStyle(TrekTheme.accent)
                    }
                    Text(RelativeDate.string(item.createdAt)).font(.caption2).foregroundStyle(.tertiary)
                }
                Spacer()
            }
        }
    }

    private var icon: String {
        switch item.eventType {
        case "badge_earned": return "rosette"
        case "new_trip": return "airplane"
        case "recommendation": return "lightbulb.fill"
        default: return "sparkle"
        }
    }

    private var detail: String {
        if let r = item.recommendation { return r.text }
        if let t = item.trip {
            let km = t.distanceKm.map { " · \(Int($0)) km" } ?? ""
            return "Logged a trip to \(t.destCity), \(t.destCountry)\(km)"
        }
        if let b = item.badge { return "Earned the “\(b.name)” badge" }
        return item.eventType
    }

    private var recommendationPlace: String? {
        guard let r = item.recommendation, let city = r.city, !city.isEmpty else { return nil }
        return city + (r.country.map { ", \($0)" } ?? "")
    }
}

enum RelativeDate {
    static func string(_ iso: String) -> String {
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = fmt.date(from: iso) ?? ISO8601DateFormatter().date(from: iso)
        guard let date else { return "" }
        let rel = RelativeDateTimeFormatter()
        rel.unitsStyle = .short
        return rel.localizedString(for: date, relativeTo: Date())
    }
}

/// Compose + post a spot recommendation to the feed.
struct RecommendComposeView: View {
    @Environment(\.dismiss) private var dismiss
    var onPosted: () async -> Void

    @State private var place: SelectedPlace?
    @State private var text = ""
    @State private var posting = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Spot (optional)") {
                    PlaceSearchField(placeholder: "Which place are you recommending?",
                                     selection: $place)
                }
                Section("Your recommendation") {
                    TextField("Share a tip about this place…", text: $text, axis: .vertical)
                        .lineLimit(3...6)
                }
                if let error { Text(error).foregroundStyle(.red).font(.caption) }
            }
            .scrollContentBackground(.hidden)
            .background(ScreenBackground())
            .navigationTitle("Recommend a spot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Post") { post() }
                        .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty || posting)
                }
            }
        }
    }

    private func post() {
        posting = true; error = nil
        Task {
            do {
                try await APIClient.shared.recommend(
                    text: text.trimmingCharacters(in: .whitespacesAndNewlines),
                    city: place?.city, country: place?.countryCode)
                await onPosted()
                dismiss()
            } catch {
                self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription
            }
            posting = false
        }
    }
}
