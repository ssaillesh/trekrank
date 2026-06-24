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
    @StateObject private var locator = LocationManager()

    @State private var camera: MapCameraPosition = .region(
        MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 20, longitude: 0),
                           span: MKCoordinateSpan(latitudeDelta: 120, longitudeDelta: 120)))
    @State private var hybrid = false
    @State private var selectedCity: MapCity?

    private var pins: [MapCity] {
        (vm.map?.cities ?? []).filter { $0.lat != nil && $0.lng != nil }
    }

    var body: some View {
        Map(position: $camera, selection: $selectedCity) {
            UserAnnotation()
            ForEach(pins) { city in
                Annotation(city.name,
                           coordinate: CLLocationCoordinate2D(latitude: city.lat!, longitude: city.lng!)) {
                    CityPin(visits: city.visits)
                        .onTapGesture { focus(on: city) }
                }
                .tag(city)
            }
        }
        .mapStyle(hybrid ? .hybrid(elevation: .realistic) : .standard(elevation: .flat))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
        .ignoresSafeArea()
        .overlay(alignment: .topTrailing) { controls }
        .overlay(alignment: .top) { permissionBanner }
        .overlay(alignment: .bottom) { statsBar }
        .safeAreaInset(edge: .bottom) { Color.clear.frame(height: 0) }
        .onAppear { locator.start() }
        .task {
            if let u = session.user?.username { await vm.load(username: u) }
        }
        .sheet(item: $selectedCity) { city in
            cityDetail(city)
                .presentationDetents([.height(220)])
                .presentationDragIndicator(.visible)
        }
    }

    // MARK: Controls

    private var controls: some View {
        VStack(spacing: 12) {
            mapButton(systemName: "location.fill", active: locator.location != nil) {
                recenterOnMe()
            }
            mapButton(systemName: hybrid ? "map.fill" : "globe.americas.fill") {
                withAnimation { hybrid.toggle() }
            }
            mapButton(systemName: "globe") {
                withAnimation { fitWorld() }
            }
        }
        .padding(.trailing, 14)
        .padding(.top, 60)
    }

    private func mapButton(systemName: String, active: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 18, weight: .semibold))
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial, in: Circle())
                .foregroundStyle(active ? TrekTheme.accent : .primary)
                .overlay(Circle().stroke(.white.opacity(0.15), lineWidth: 1))
                .shadow(color: .black.opacity(0.2), radius: 6, y: 3)
        }
    }

    @ViewBuilder private var permissionBanner: some View {
        if locator.isDenied {
            Text("Location access is off — enable it in Settings to see where you are.")
                .font(.caption).multilineTextAlignment(.center)
                .padding(10).background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
                .padding(.horizontal, 40).padding(.top, 60)
                .transition(.move(edge: .top).combined(with: .opacity))
        }
    }

    private var statsBar: some View {
        Group {
            if let map = vm.map {
                HStack(spacing: 28) {
                    stat("\(map.countries.count)", "Countries")
                    Divider().frame(height: 28)
                    stat("\(map.cities.count)", "Cities")
                    if locator.location != nil {
                        Divider().frame(height: 28)
                        stat("📍", "You")
                    }
                }
                .padding(.horizontal, 22).padding(.vertical, 12)
                .background(.ultraThinMaterial, in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.12), lineWidth: 1))
                .shadow(color: .black.opacity(0.2), radius: 10, y: 4)
                .padding(.bottom, 28)
            }
        }
    }

    private func cityDetail(_ city: MapCity) -> some View {
        VStack(spacing: 14) {
            Capsule().fill(.secondary).frame(width: 36, height: 4).padding(.top, 6)
            Image(systemName: "mappin.circle.fill")
                .font(.system(size: 40)).foregroundStyle(TrekTheme.accent)
            Text(city.name).font(.title2.bold())
            Text(city.visits == 1 ? "Visited once" : "Visited \(city.visits) times")
                .foregroundStyle(.secondary)
            Button {
                focus(on: city); selectedCity = nil
            } label: {
                Label("Zoom to city", systemImage: "scope")
                    .frame(maxWidth: .infinity).padding()
                    .background(TrekTheme.accent).foregroundStyle(.black)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal)
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.headline.bold()).foregroundStyle(TrekTheme.accent)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
    }

    // MARK: Actions

    private func recenterOnMe() {
        locator.start()
        guard let me = locator.location else { return }
        withAnimation(.easeInOut) {
            camera = .region(MKCoordinateRegion(
                center: me, span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)))
        }
    }

    private func focus(on city: MapCity) {
        guard let lat = city.lat, let lng = city.lng else { return }
        withAnimation(.easeInOut) {
            camera = .region(MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
                span: MKCoordinateSpan(latitudeDelta: 0.5, longitudeDelta: 0.5)))
        }
    }

    private func fitWorld() {
        camera = .region(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 20, longitude: 0),
            span: MKCoordinateSpan(latitudeDelta: 120, longitudeDelta: 120)))
    }
}

/// A pulsing pin whose size reflects how many times a city was visited.
struct CityPin: View {
    let visits: Int
    @State private var pulse = false

    private var size: CGFloat { min(14 + CGFloat(visits) * 3, 30) }

    var body: some View {
        ZStack {
            Circle().fill(TrekTheme.accent.opacity(0.25))
                .frame(width: size * 2, height: size * 2)
                .scaleEffect(pulse ? 1.0 : 0.5)
                .opacity(pulse ? 0 : 0.8)
            Circle().fill(TrekTheme.accent).frame(width: size, height: size)
                .overlay(Circle().stroke(.white, lineWidth: 2))
                .shadow(radius: 3)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 1.6).repeatForever(autoreverses: false)) {
                pulse = true
            }
        }
    }
}
