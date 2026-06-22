import SwiftUI
import MapKit

@MainActor
final class MapViewModel: ObservableObject {
    @Published var map: UserMap?
    @Published var loading = false

    func load(username: String) async {
        loading = true
        map = try? await APIClient.shared.map(username: username)
        loading = false
    }
}

struct MapView: View {
    @EnvironmentObject var session: SessionStore
    @StateObject private var vm = MapViewModel()
    @State private var camera: MapCameraPosition = .region(
        MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 20, longitude: 0),
                           span: MKCoordinateSpan(latitudeDelta: 120, longitudeDelta: 120)))

    private var pins: [MapCity] {
        (vm.map?.cities ?? []).filter { $0.lat != nil && $0.lng != nil }
    }

    var body: some View {
        NavigationStack {
            Map(position: $camera) {
                ForEach(pins) { city in
                    Annotation(city.name,
                               coordinate: CLLocationCoordinate2D(latitude: city.lat!, longitude: city.lng!)) {
                        ZStack {
                            Circle().fill(TrekTheme.accent).frame(width: 14, height: 14)
                            Circle().stroke(.white, lineWidth: 2).frame(width: 14, height: 14)
                        }
                    }
                }
            }
            .overlay(alignment: .bottom) {
                if let map = vm.map {
                    HStack(spacing: 24) {
                        stat("\(map.countries.count)", "Countries")
                        stat("\(map.cities.count)", "Cities")
                    }
                    .padding().background(.ultraThinMaterial)
                    .clipShape(Capsule()).padding(.bottom, 8)
                }
            }
            .navigationTitle("My Map")
            .task {
                if let u = session.user?.username { await vm.load(username: u) }
            }
        }
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack {
            Text(value).font(.title3.bold()).foregroundStyle(TrekTheme.accent)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
    }
}
