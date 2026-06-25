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
        // Flat elevation only — `.realistic` 3D elevation is extremely GPU-heavy
        // in the Simulator and was a major source of overheating.
        .mapStyle(hybrid ? .hybrid(elevation: .flat) : .standard(elevation: .flat))
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
                .foregroundStyle(active ? TrekTheme.accent : Color.primary)
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

/// A pin whose size reflects how many times a city was visited.
///
/// Deliberately static (no `.repeatForever` pulse): each visible pin would
/// otherwise run its own perpetual animation, and with many cities on screen
/// that multiplies into constant GPU work that overheats the Simulator.
struct CityPin: View {
    let visits: Int

    private var size: CGFloat { min(14 + CGFloat(visits) * 3, 30) }

    var body: some View {
        ZStack {
            Circle().fill(TrekTheme.accent.opacity(0.22))
                .frame(width: size * 1.7, height: size * 1.7)
            Circle().fill(TrekTheme.accent).frame(width: size, height: size)
                .overlay(Circle().stroke(.white, lineWidth: 2))
                .shadow(radius: 3)
        }
    }
}

// MARK: - Profile travel map

/// Compact travel map embedded in a profile: pins every visited city. Auto-frames
/// to fit the user's places. Used on both the signed-in and public profiles.
struct ProfileMapCard: View {
    let username: String
    @StateObject private var vm = MapViewModel()
    @State private var camera: MapCameraPosition = .automatic

    private var pins: [MapCity] {
        (vm.map?.cities ?? []).filter { $0.lat != nil && $0.lng != nil }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Travel Map").font(.title3.bold())
                Spacer()
                if let m = vm.map {
                    Text("\(m.countries.count) countries · \(m.cities.count) cities")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Map(position: $camera) {
                ForEach(pins) { city in
                    Annotation(city.name,
                               coordinate: CLLocationCoordinate2D(latitude: city.lat!, longitude: city.lng!)) {
                        CityPin(visits: city.visits)
                    }
                }
            }
            .mapStyle(.standard(elevation: .flat))
            .frame(height: 260)
            .clipShape(RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(.white.opacity(0.1), lineWidth: 1))
            .overlay {
                if pins.isEmpty && !vm.loading {
                    Text("No places on the map yet").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .task(id: username) { await vm.load(username: username) }
    }
}

// MARK: - Live trip recording

/// Tracks the device's GPS while recording and accumulates the real distance
/// travelled along the route (not straight-line). Drives the Record screen.
@MainActor
final class TripRecorder: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var isRecording = false
    @Published var distanceMeters: Double = 0
    @Published var path: [CLLocationCoordinate2D] = []
    @Published var elapsed: TimeInterval = 0
    @Published var authorization: CLAuthorizationStatus

    private let manager = CLLocationManager()
    private var lastLocation: CLLocation?
    private var startDate: Date?
    private var ticker: Timer?

    var distanceKm: Double { distanceMeters / 1000 }
    var isDenied: Bool { authorization == .denied || authorization == .restricted }
    var startCoordinate: CLLocationCoordinate2D? { path.first }
    var endCoordinate: CLLocationCoordinate2D? { path.last }

    override init() {
        authorization = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        manager.activityType = .fitness
        manager.distanceFilter = 5
    }

    func start() {
        if manager.authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        }
        distanceMeters = 0; path = []; lastLocation = nil; elapsed = 0
        startDate = Date()
        isRecording = true
        manager.startUpdatingLocation()
        ticker = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, let s = self.startDate else { return }
                self.elapsed = Date().timeIntervalSince(s)
            }
        }
    }

    func finish() {
        isRecording = false
        manager.stopUpdatingLocation()
        ticker?.invalidate(); ticker = nil
    }

    func reset() {
        finish()
        distanceMeters = 0; path = []; elapsed = 0; lastLocation = nil; startDate = nil
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        Task { @MainActor in self.ingest(locs) }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        let status = m.authorizationStatus
        Task { @MainActor in
            self.authorization = status
            if self.isRecording, status == .authorizedWhenInUse || status == .authorizedAlways {
                m.startUpdatingLocation()
            }
        }
    }

    private func ingest(_ locs: [CLLocation]) {
        guard isRecording else { return }
        for loc in locs {
            guard loc.horizontalAccuracy >= 0, loc.horizontalAccuracy < 50 else { continue }
            if let last = lastLocation {
                let d = loc.distance(from: last)
                if d >= 1 && d < 500 {   // ignore GPS jitter and unrealistic jumps
                    distanceMeters += d
                    path.append(loc.coordinate)
                }
            } else {
                path.append(loc.coordinate)
            }
            lastLocation = loc
        }
    }
}

/// The Record tab: start tracking, watch the live distance climb along the
/// drawn route, then tap Done to turn it into a completed trip.
struct RecordView: View {
    @StateObject private var rec = TripRecorder()
    @State private var camera: MapCameraPosition = .userLocation(fallback: .automatic)
    @State private var showSave = false
    @AppStorage(Units.storageKey) private var useMiles = false

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                Map(position: $camera) {
                    UserAnnotation()
                    if rec.path.count > 1 {
                        MapPolyline(coordinates: rec.path)
                            .stroke(TrekTheme.accent, lineWidth: 5)
                    }
                }
                .mapStyle(.standard(elevation: .flat))
                .ignoresSafeArea()

                panel
            }
            .navigationTitle("Record")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showSave) {
                SaveRecordedTripView(distanceKm: rec.distanceKm,
                                     start: rec.startCoordinate,
                                     end: rec.endCoordinate) {
                    rec.reset()
                }
            }
        }
    }

    private var panel: some View {
        VStack(spacing: 14) {
            HStack(spacing: 24) {
                stat(Units.format(km: rec.distanceKm), "Distance")
                Divider().frame(height: 36)
                stat(timeString(rec.elapsed), "Time")
            }
            if rec.isDenied {
                Text("Location access is off — enable it in Settings to record.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            if rec.isRecording {
                Button { rec.finish(); showSave = true } label: {
                    Label("Done", systemImage: "stop.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(NeonButtonStyle())
            } else {
                Button { rec.start() } label: {
                    Label("Start recording", systemImage: "record.circle").frame(maxWidth: .infinity)
                }
                .buttonStyle(NeonButtonStyle())
                .disabled(rec.isDenied)
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22))
        .padding()
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(spacing: 3) {
            Text(value).font(.title2.bold().monospacedDigit()).foregroundStyle(TrekTheme.accent)
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func timeString(_ t: TimeInterval) -> String {
        let s = Int(t)
        return String(format: "%02d:%02d", s / 60, s % 60)
    }
}

/// Confirmation sheet after a recording: shows the resolved From/To + distance,
/// lets the user title it and pick transport, then saves it as a trip with the
/// actual recorded distance.
struct SaveRecordedTripView: View {
    @Environment(\.dismiss) private var dismiss
    let distanceKm: Double
    let start: CLLocationCoordinate2D?
    let end: CLLocationCoordinate2D?
    var onSaved: () -> Void

    @State private var title = ""
    @State private var transport = "walk"
    @State private var origin: (city: String, code: String, display: String)?
    @State private var dest: (city: String, code: String, display: String)?
    @State private var resolving = true
    @State private var saving = false
    @State private var error: String?

    private let transports = ["walk", "bike", "car", "bus", "train", "boat", "flight", "other"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Recorded") {
                    LabeledContent("Distance", value: Units.format(km: distanceKm))
                    LabeledContent("From", value: origin?.display ?? (resolving ? "Locating…" : "Unknown"))
                    LabeledContent("To", value: dest?.display ?? (resolving ? "Locating…" : "Unknown"))
                }
                Section("Details") {
                    TextField("Title (optional)", text: $title)
                    Picker("Transport", selection: $transport) {
                        ForEach(transports, id: \.self) { Text($0.capitalized).tag($0) }
                    }
                }
                if let error { Text(error).foregroundStyle(.red).font(.caption) }
            }
            .scrollContentBackground(.hidden)
            .background(ScreenBackground())
            .navigationTitle("Save trip")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Discard") { dismiss(); onSaved() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(saving || resolving || dest == nil)
                }
            }
            .task { await resolve() }
        }
    }

    private func resolve() async {
        resolving = true
        if let s = start { origin = await Self.reverse(s) }
        if let e = end { dest = await Self.reverse(e) }
        resolving = false
    }

    private func save() {
        guard let d = dest else { return }
        saving = true; error = nil
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        let body = CreateTripBody(
            title: title.isEmpty ? nil : title,
            originCity: origin?.city, originCountry: origin?.code,
            destCity: d.city, destCountry: d.code,
            transportMode: transport, startDate: fmt.string(from: Date()),
            endDate: nil, notes: nil,
            originLat: start?.latitude, originLng: start?.longitude,
            destLat: end?.latitude, destLng: end?.longitude,
            distanceKm: distanceKm)
        Task {
            do {
                _ = try await APIClient.shared.createTrip(body)
                dismiss(); onSaved()
            } catch {
                self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription
                saving = false
            }
        }
    }

    /// Reverse-geocode a coordinate to (city, ISO country code, display string).
    private static func reverse(_ c: CLLocationCoordinate2D) async -> (city: String, code: String, display: String)? {
        let geocoder = CLGeocoder()
        let loc = CLLocation(latitude: c.latitude, longitude: c.longitude)
        guard let pm = try? await geocoder.reverseGeocodeLocation(loc).first,
              let code = pm.isoCountryCode else { return nil }
        let city = pm.locality ?? pm.administrativeArea ?? pm.name ?? "Unknown"
        let display = [city, pm.administrativeArea, pm.country].compactMap { $0 }.joined(separator: ", ")
        return (city, code, display)
    }
}
