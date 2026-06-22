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

                List {
                    if let rankings = vm.board?.rankings {
                        ForEach(rankings) { entry in
                            LeaderboardRow(entry: entry, metric: vm.metric,
                                           isMe: entry.rank == vm.board?.myRank)
                        }
                    }
                }
                .listStyle(.plain)
                .overlay { if vm.loading { ProgressView() } }
            }
            .navigationTitle("Leaderboard")
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
        HStack(spacing: 14) {
            Text("#\(entry.rank)").font(.headline.monospacedDigit())
                .foregroundStyle(medalColor).frame(width: 40, alignment: .leading)
            Circle().fill(TrekTheme.accent.opacity(0.25))
                .frame(width: 34, height: 34)
                .overlay(Text(String(entry.user.username.prefix(1)).uppercased()).bold())
            Text("@\(entry.user.username)").fontWeight(isMe ? .bold : .regular)
            Spacer()
            Text(valueText).font(.headline.monospacedDigit()).foregroundStyle(TrekTheme.accent)
        }
        .listRowBackground(isMe ? TrekTheme.accent.opacity(0.12) : Color.clear)
    }

    private var valueText: String {
        metric == "km" ? "\(Int(entry.value)) km" : "\(Int(entry.value))"
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
