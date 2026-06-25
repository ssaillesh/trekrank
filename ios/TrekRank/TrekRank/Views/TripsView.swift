import SwiftUI

/// A just-earned achievement to celebrate (one or more badges unlocked at once).
struct Celebration: Identifiable {
    let id = UUID()
    let badges: [Badge]
}

@MainActor
final class TripsViewModel: ObservableObject {
    @Published var trips: [Trip] = []
    @Published var loading = false

    private var pollTask: Task<Void, Never>?

    func load() async {
        loading = true
        if let list = try? await APIClient.shared.trips() { trips = list.items }
        loading = false
        schedulePollIfNeeded()
    }

    /// Geocoding + distance are computed asynchronously on the server, so a
    /// freshly-added trip comes back as "processing" with no distance yet.
    /// While any trip is still processing, quietly re-fetch every ~1.2s so the
    /// distance appears on its own. Stops once nothing is processing (~18s cap).
    private func schedulePollIfNeeded() {
        pollTask?.cancel()
        guard trips.contains(where: { $0.status == "processing" }) else { return }
        pollTask = Task { [weak self] in
            for _ in 0..<15 {
                try? await Task.sleep(nanoseconds: 1_200_000_000)
                guard let self, !Task.isCancelled else { return }
                if let list = try? await APIClient.shared.trips() { self.trips = list.items }
                if !self.trips.contains(where: { $0.status == "processing" }) { return }
            }
        }
    }

    func delete(_ trip: Trip) async {
        pollTask?.cancel()
        try? await APIClient.shared.deleteTrip(id: trip.id)
        await load()
    }
}

/// Management list of the user's own trips (distances, delete), opened as a
/// sheet from the Home feed. Logging happens on the feed itself.
struct MyTripsView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var vm = TripsViewModel()
    @AppStorage(Units.storageKey) private var useMiles = false  // re-render on unit change

    var body: some View {
        NavigationStack {
            List {
                if vm.trips.isEmpty && !vm.loading {
                    ContentUnavailableView("No trips yet", systemImage: "airplane.departure",
                        description: Text("Log a trip from the Home tab."))
                        .listRowBackground(Color.clear)
                }
                ForEach(vm.trips) { trip in
                    TripRow(trip: trip)
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                }
                .onDelete { idx in
                    Task { for i in idx { await vm.delete(vm.trips[i]) } }
                }
            }
            .listStyle(.plain)
            .trekScreen()
            .navigationTitle("My Trips")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
            .refreshable { await vm.load() }
            .task { await vm.load() }
        }
    }
}

/// Celebratory popup shown when the user unlocks one or more badges by logging a
/// trip. The achievement is already on their feed, so the primary action takes
/// them there to see/share it.
struct AchievementView: View {
    let badges: [Badge]
    var onViewFeed: () -> Void
    var onDismiss: () -> Void

    @State private var pop = false

    private var hero: Badge? { badges.first }

    var body: some View {
        VStack(spacing: 18) {
            Spacer(minLength: 8)

            Text(hero?.emoji ?? "🏅")
                .font(.system(size: 96))
                .scaleEffect(pop ? 1 : 0.4)
                .rotationEffect(.degrees(pop ? 0 : -25))
                .animation(.spring(response: 0.5, dampingFraction: 0.55), value: pop)

            Text("Achievement Unlocked!")
                .font(.title3.bold())
                .foregroundStyle(TrekTheme.accent)

            Text(hero?.name ?? "New badge")
                .font(.title.bold())
            if let desc = hero?.description {
                Text(desc)
                    .font(.subheadline).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            if badges.count > 1 {
                Text("+ \(badges.count - 1) more achievement\(badges.count - 1 == 1 ? "" : "s")")
                    .font(.caption.bold())
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(TrekTheme.accent.opacity(0.15), in: Capsule())
            }

            Spacer(minLength: 4)

            VStack(spacing: 10) {
                Button { onViewFeed() } label: {
                    Label("See it on your feed", systemImage: "list.bullet.rectangle")
                }
                .buttonStyle(NeonButtonStyle())

                Button("Maybe later") { onDismiss() }
                    .font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .padding(28)
        .frame(maxWidth: .infinity)
        .background(ScreenBackground())
        .onAppear { pop = true }
    }
}

struct TripRow: View {
    let trip: Trip

    var body: some View {
        GlassCard {
            HStack(spacing: 12) {
                Image(systemName: transportIcon).font(.title3)
                    .foregroundStyle(TrekTheme.accent).frame(width: 40, height: 40)
                    .background(TrekTheme.accent.opacity(0.12), in: Circle())
                VStack(alignment: .leading, spacing: 3) {
                    Text(trip.title ?? "\(trip.destCity), \(trip.destCountry)").font(.headline)
                    HStack(spacing: 6) {
                        if let o = trip.originCity { Text(o); Image(systemName: "arrow.right").font(.caption2) }
                        Text("\(trip.destCity), \(trip.destCountry)")
                    }.font(.subheadline).foregroundStyle(.secondary)
                    Text(trip.startDate).font(.caption2).foregroundStyle(.tertiary)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    if let km = trip.distanceKm {
                        CountUpText(value: Units.value(km: km), suffix: Units.suffix)
                            .font(.subheadline.bold()).foregroundStyle(TrekTheme.accent)
                    } else if trip.status == "processing" {
                        ProgressView().controlSize(.small).tint(TrekTheme.accent)
                    }
                }
            }
        }
    }

    private var transportIcon: String {
        switch trip.transportMode {
        case "flight": return "airplane"
        case "train": return "tram.fill"
        case "car": return "car.fill"
        case "bus": return "bus.fill"
        case "boat": return "ferry.fill"
        case "bike": return "bicycle"
        case "walk": return "figure.walk"
        default: return "mappin.and.ellipse"
        }
    }
}
