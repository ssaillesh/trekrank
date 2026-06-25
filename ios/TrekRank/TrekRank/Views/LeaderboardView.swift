import SwiftUI

@MainActor
final class LeaderboardViewModel: ObservableObject {
    @Published var board: LeaderboardResponse?
    @Published var loading = false
    @Published var scope = "friends"   // friends | global
    @Published var metric = "countries"
    @Published var period = "all_time"

    func load() async {
        loading = true
        do {
            if scope == "friends" {
                board = try await APIClient.shared.leaderboard(metric: metric, period: period)
            } else {
                board = try await APIClient.shared.globalLeaderboard(metric: metric)
            }
        } catch { board = nil }
        loading = false
    }
}

struct LeaderboardView: View {
    @StateObject private var vm = LeaderboardViewModel()
    @AppStorage(Units.storageKey) private var useMiles = false  // re-render on unit change
    private let metrics = ["countries", "cities", "km", "trips"]

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                Picker("Scope", selection: $vm.scope) {
                    Text("Friends").tag("friends"); Text("Global").tag("global")
                }.pickerStyle(.segmented).padding(.horizontal)

                Picker("Metric", selection: $vm.metric) {
                    ForEach(metrics, id: \.self) { Text($0.capitalized).tag($0) }
                }.pickerStyle(.segmented).padding(.horizontal)

                ScrollView {
                    LazyVStack(spacing: 10) {
                        if let rankings = vm.board?.rankings {
                            ForEach(rankings) { entry in
                                NavigationLink(value: entry.user.username) {
                                    LeaderboardRow(entry: entry, metric: vm.metric,
                                                   isMe: entry.rank == vm.board?.myRank)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 4)
                }
                .overlay { if vm.loading { ProgressView().tint(TrekTheme.accent) } }
            }
            .trekScreen()
            .navigationTitle("Leaderboard")
            .navigationDestination(for: String.self) { PublicProfileView(username: $0) }
            .task { await vm.load() }
            .onChange(of: vm.scope) { _, _ in Task { await vm.load() } }
            .onChange(of: vm.metric) { _, _ in Task { await vm.load() } }
        }
    }
}

struct LeaderboardRow: View {
    let entry: LeaderboardEntry
    let metric: String
    let isMe: Bool

    var body: some View {
        GlassCard {
            HStack(spacing: 14) {
                ZStack {
                    if entry.rank <= 3 {
                        Image(systemName: "medal.fill").font(.title3).foregroundStyle(medalColor)
                    } else {
                        Text("#\(entry.rank)").font(.headline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }.frame(width: 40, alignment: .leading)
                Circle().fill(TrekTheme.accent.opacity(0.25))
                    .frame(width: 36, height: 36)
                    .overlay(Text(String(entry.user.username.prefix(1)).uppercased()).bold())
                Text("@\(entry.user.username)").fontWeight(isMe ? .bold : .regular)
                if isMe {
                    Text("YOU").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2)
                        .background(TrekTheme.accent.opacity(0.2), in: Capsule())
                        .foregroundStyle(TrekTheme.accent)
                }
                Spacer()
                Text(valueText).font(.headline.monospacedDigit()).foregroundStyle(TrekTheme.accent)
            }
        }
        .overlay(alignment: .leading) {
            if isMe {
                RoundedRectangle(cornerRadius: 3).fill(TrekTheme.accent)
                    .frame(width: 4).padding(.vertical, 10)
            }
        }
    }

    private var valueText: String {
        metric == "km" ? Units.format(km: entry.value) : "\(Int(entry.value))"
    }

    private var medalColor: Color {
        switch entry.rank {
        case 1: return .yellow
        case 2: return .gray
        case 3: return .brown
        default: return .secondary
        }
    }
}
