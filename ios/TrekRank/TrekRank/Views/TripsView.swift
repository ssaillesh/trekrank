import SwiftUI

@MainActor
final class TripsViewModel: ObservableObject {
    @Published var trips: [Trip] = []
    @Published var loading = false

    func load() async {
        loading = true
        if let list = try? await APIClient.shared.trips() { trips = list.items }
        loading = false
    }

    func delete(_ trip: Trip) async {
        try? await APIClient.shared.deleteTrip(id: trip.id)
        await load()
    }
}

struct TripsView: View {
    @StateObject private var vm = TripsViewModel()
    @State private var showAdd = false

    var body: some View {
        NavigationStack {
            List {
                if vm.trips.isEmpty && !vm.loading {
                    ContentUnavailableView("No trips yet", systemImage: "airplane.departure",
                        description: Text("Tap + to log your first trip."))
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
            .navigationTitle("Trips")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showAdd = true } label: {
                        Image(systemName: "plus.circle.fill").font(.title2)
                            .foregroundStyle(TrekTheme.accent)
                    }
                }
            }
            .sheet(isPresented: $showAdd) {
                AddTripView { await vm.load() }
            }
            .refreshable { await vm.load() }
            .task { await vm.load() }
        }
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
                        CountUpText(value: km, suffix: " km")
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
