import SwiftUI

@MainActor
final class FeedViewModel: ObservableObject {
    @Published var items: [FeedItem] = []
    @Published var loading = false
    @Published var error: String?

    func load() async {
        loading = true; error = nil
        do { items = try await APIClient.shared.feed().items }
        catch { self.error = (error as? APIError)?.errorDescription ?? error.localizedDescription }
        loading = false
    }
}

struct FeedView: View {
    @StateObject private var vm = FeedViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 14) {
                    if vm.items.isEmpty && !vm.loading {
                        ContentUnavailableView("No activity yet",
                            systemImage: "sparkles",
                            description: Text("Add friends and log trips to see your feed light up."))
                            .padding(.top, 80)
                    }
                    ForEach(Array(vm.items.enumerated()), id: \.element.id) { idx, item in
                        FeedRow(item: item)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                            .animation(.spring(response: 0.5, dampingFraction: 0.8)
                                .delay(Double(min(idx, 8)) * 0.04), value: vm.items.count)
                    }
                }
                .padding(.horizontal).padding(.top, 8)
            }
            .trekScreen()
            .navigationTitle("Feed")
            .refreshable { await vm.load() }
            .overlay { if vm.loading && vm.items.isEmpty { ProgressView().tint(TrekTheme.accent) } }
            .task { await vm.load() }
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
                    Text(detail).font(.subheadline).foregroundStyle(.secondary)
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
        default: return "sparkle"
        }
    }

    private var detail: String {
        if let t = item.trip {
            let km = t.distanceKm.map { " · \(Int($0)) km" } ?? ""
            return "Logged a trip to \(t.destCity), \(t.destCountry)\(km)"
        }
        if let b = item.badge { return "Earned the “\(b.name)” badge" }
        return item.eventType
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
