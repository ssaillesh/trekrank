import SwiftUI
import MapKit

struct AddTripView: View {
    @Environment(\.dismiss) private var dismiss
    var onSaved: () async -> Void

    @State private var title = ""
    @State private var originPlace: SelectedPlace?
    @State private var destPlace: SelectedPlace?
    @State private var transport = "flight"
    @State private var startDate = Date()
    @State private var saving = false
    @State private var error: String?

    private let transports = ["flight", "train", "car", "bus", "boat", "bike", "walk", "other"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Trip") {
                    TextField("Title (optional)", text: $title)
                    Picker("Transport", selection: $transport) {
                        ForEach(transports, id: \.self) { Text($0.capitalized).tag($0) }
                    }
                    DatePicker("Start date", selection: $startDate, displayedComponents: .date)
                }
                Section("From (optional)") {
                    PlaceSearchField(placeholder: "Search a city, e.g. London",
                                     selection: $originPlace)
                }
                Section("To") {
                    PlaceSearchField(placeholder: "Search a city, e.g. London",
                                     selection: $destPlace)
                }
                if let error { Text(error).foregroundStyle(.red).font(.caption) }
            }
            .scrollContentBackground(.hidden)
            .background(ScreenBackground())
            .navigationTitle("New Trip")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(destPlace == nil || saving)
                }
            }
        }
    }

    private func save() {
        guard let dest = destPlace else { return }
        saving = true; error = nil
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        // The picker already resolved exact coordinates + ISO country code, so
        // the server skips its slow geocoding and computes distance instantly.
        let body = CreateTripBody(
            title: title.isEmpty ? nil : title,
            originCity: originPlace?.city,
            originCountry: originPlace?.countryCode,
            destCity: dest.city, destCountry: dest.countryCode,
            transportMode: transport, startDate: fmt.string(from: startDate),
            endDate: nil, notes: nil,
            originLat: originPlace?.latitude, originLng: originPlace?.longitude,
            destLat: dest.latitude, destLng: dest.longitude)
        Task {
            do {
                _ = try await APIClient.shared.createTrip(body)
                await onSaved()
                dismiss()
            } catch {
                self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription
            }
            saving = false
        }
    }
}

// MARK: - Place picking

/// A place the user selected from the search suggestions: a real city with its
/// ISO-2 country code and exact coordinates (so the backend never has to geocode).
struct SelectedPlace: Equatable {
    let city: String
    let countryCode: String   // ISO-3166 alpha-2, e.g. "GB", "CA"
    let display: String       // "London, England, United Kingdom"
    let latitude: Double
    let longitude: Double
}

/// Live, type-ahead city search backed by MapKit. Typing "london" yields
/// "London, England, United Kingdom", "London, ON, Canada", etc. Selecting a
/// suggestion resolves it to a `SelectedPlace`.
@MainActor
final class PlaceSearchCompleter: NSObject, ObservableObject, MKLocalSearchCompleterDelegate {
    @Published var query: String = "" {
        didSet {
            let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
            if q.isEmpty { suggestions = []; return }
            completer.queryFragment = q
        }
    }
    @Published var suggestions: [MKLocalSearchCompletion] = []

    private let completer = MKLocalSearchCompleter()

    override init() {
        super.init()
        completer.delegate = self
        completer.resultTypes = .address   // cities/regions, not businesses
    }

    /// Resolve a suggestion into a concrete place (city, country code, coords).
    func resolve(_ completion: MKLocalSearchCompletion) async -> SelectedPlace? {
        let search = MKLocalSearch(request: .init(completion: completion))
        guard let response = try? await search.start(),
              let pm = response.mapItems.first?.placemark,
              let code = pm.isoCountryCode else { return nil }
        let city = pm.locality ?? pm.name ?? completion.title
        let parts = [city, pm.administrativeArea, pm.country].compactMap { $0 }
        return SelectedPlace(
            city: city, countryCode: code,
            display: parts.joined(separator: ", "),
            latitude: pm.coordinate.latitude, longitude: pm.coordinate.longitude)
    }

    nonisolated func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        let results = completer.results
        Task { @MainActor in self.suggestions = results }
    }

    nonisolated func completer(_ completer: MKLocalSearchCompleter, didFailWithError error: Error) {
        Task { @MainActor in self.suggestions = [] }
    }
}

/// A text field that shows live location suggestions as the user types and,
/// once a place is chosen, collapses into a confirmed "chip" with a clear button.
struct PlaceSearchField: View {
    let placeholder: String
    @Binding var selection: SelectedPlace?

    @StateObject private var completer = PlaceSearchCompleter()
    @State private var resolving = false
    @FocusState private var focused: Bool

    var body: some View {
        if let place = selection {
            HStack {
                Image(systemName: "mappin.circle.fill").foregroundStyle(TrekTheme.accent)
                Text(place.display).lineLimit(1)
                Spacer()
                Button {
                    selection = nil
                    completer.query = ""
                    focused = true
                } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
        } else {
            TextField(placeholder, text: $completer.query)
                .focused($focused)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.words)

            if resolving {
                HStack { ProgressView().controlSize(.small); Text("Locating…").foregroundStyle(.secondary) }
            }

            ForEach(completer.suggestions.prefix(8), id: \.self) { s in
                Button {
                    Task {
                        resolving = true
                        if let place = await completer.resolve(s) {
                            selection = place
                            completer.query = ""
                            focused = false
                        }
                        resolving = false
                    }
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "mappin.and.ellipse").foregroundStyle(.secondary)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(s.title)
                            if !s.subtitle.isEmpty {
                                Text(s.subtitle).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }
}
