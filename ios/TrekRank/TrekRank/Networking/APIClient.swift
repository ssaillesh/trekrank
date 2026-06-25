import Foundation

enum APIError: LocalizedError {
    case http(Int, String)
    case decoding(String)
    case transport(String)

    var errorDescription: String? {
        switch self {
        case .http(let code, let msg): return "Server error \(code): \(msg)"
        case .decoding(let m): return "Decoding error: \(m)"
        case .transport(let m): return "Network error: \(m)"
        }
    }
}

/// Thin async REST client for the TrekRank API. Holds the bearer token.
actor APIClient {
    static let shared = APIClient()

    private let base = Config.apiBaseURL
    private var accessToken: String?

    func setToken(_ token: String?) { accessToken = token }

    // MARK: Core request

    private func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        query: [URLQueryItem] = [],
        body: Encodable? = nil,
        authorized: Bool = true,
        decode: T.Type
    ) async throws -> T {
        var comps = URLComponents(url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { comps.queryItems = query }
        var req = URLRequest(url: comps.url!)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if authorized, let token = accessToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            req.httpBody = try JSONEncoder().encode(AnyEncodable(body))
        }

        let (data, resp): (Data, URLResponse)
        do {
            (data, resp) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError.transport(error.localizedDescription)
        }
        guard let http = resp as? HTTPURLResponse else {
            throw APIError.transport("No HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(http.statusCode, msg)
        }
        if T.self == EmptyResponse.self { return EmptyResponse() as! T }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error.localizedDescription)
        }
    }

    // MARK: Auth

    func register(email: String, username: String, displayName: String, password: String) async throws -> TokenResponse {
        struct Body: Encodable { let email, username, display_name, password: String }
        return try await request("auth/register", method: "POST",
            body: Body(email: email, username: username, display_name: displayName, password: password),
            authorized: false, decode: TokenResponse.self)
    }

    func login(email: String, password: String) async throws -> TokenResponse {
        struct Body: Encodable { let email, password: String }
        return try await request("auth/login", method: "POST",
            body: Body(email: email, password: password), authorized: false, decode: TokenResponse.self)
    }

    func forgotPassword(email: String) async throws -> ForgotPasswordResponse {
        struct Body: Encodable { let email: String }
        return try await request("auth/forgot-password", method: "POST",
            body: Body(email: email), authorized: false, decode: ForgotPasswordResponse.self)
    }

    func resetPassword(token: String, newPassword: String) async throws -> TokenResponse {
        struct Body: Encodable { let reset_token: String; let new_password: String }
        return try await request("auth/reset-password", method: "POST",
            body: Body(reset_token: token, new_password: newPassword),
            authorized: false, decode: TokenResponse.self)
    }

    func changePassword(current: String, newPassword: String) async throws -> TokenResponse {
        struct Body: Encodable { let current_password: String; let new_password: String }
        return try await request("auth/change-password", method: "POST",
            body: Body(current_password: current, new_password: newPassword),
            decode: TokenResponse.self)
    }

    func deleteAccount() async throws {
        _ = try await request("auth/account", method: "DELETE", decode: EmptyResponse.self)
    }

    func updateProfile(email: String? = nil, displayName: String? = nil,
                       bio: String? = nil, homeCity: String? = nil,
                       homeCountry: String? = nil) async throws -> UserProfile {
        struct Body: Encodable {
            var email: String?
            var display_name: String?
            var bio: String?
            var home_city: String?
            var home_country: String?
        }
        return try await request("users/me", method: "PATCH",
            body: Body(email: email, display_name: displayName, bio: bio,
                       home_city: homeCity, home_country: homeCountry),
            decode: UserProfile.self)
    }

    // MARK: Users

    func me() async throws -> UserProfile {
        try await request("users/me", decode: UserProfile.self)
    }

    func user(username: String) async throws -> UserProfile {
        try await request("users/\(username)", decode: UserProfile.self)
    }

    func userBadges(username: String) async throws -> [Badge] {
        try await request("users/\(username)/badges", decode: [Badge].self)
    }

    func stats(username: String) async throws -> UserStats {
        try await request("users/\(username)/stats", decode: UserStats.self)
    }

    func map(username: String) async throws -> UserMap {
        try await request("users/\(username)/map", decode: UserMap.self)
    }

    func searchUsers(_ q: String) async throws -> [LeaderboardUser] {
        try await request("users/search", query: [URLQueryItem(name: "q", value: q)],
                          decode: [LeaderboardUser].self)
    }

    // MARK: Trips

    func trips(cursor: String? = nil) async throws -> TripList {
        var q: [URLQueryItem] = []
        if let cursor { q.append(URLQueryItem(name: "cursor", value: cursor)) }
        return try await request("trips", query: q, decode: TripList.self)
    }

    func createTrip(_ body: CreateTripBody) async throws -> Trip {
        try await request("trips", method: "POST", body: body, decode: Trip.self)
    }

    func trip(id: String) async throws -> Trip {
        try await request("trips/\(id)", decode: Trip.self)
    }

    func deleteTrip(id: String) async throws {
        _ = try await request("trips/\(id)", method: "DELETE", decode: EmptyResponse.self)
    }

    // MARK: Friends

    func sendFriendRequest(username: String) async throws {
        struct Body: Encodable { let username: String }
        _ = try await request("friends/request", method: "POST", body: Body(username: username),
                              decode: EmptyResponse.self)
    }

    // MARK: Leaderboard / Feed / Badges / Share

    func leaderboard(metric: String, period: String) async throws -> LeaderboardResponse {
        try await request("leaderboards/friends",
            query: [URLQueryItem(name: "metric", value: metric),
                    URLQueryItem(name: "period", value: period)],
            decode: LeaderboardResponse.self)
    }

    func globalLeaderboard(metric: String) async throws -> LeaderboardResponse {
        try await request("leaderboards/global",
            query: [URLQueryItem(name: "metric", value: metric)], authorized: false,
            decode: LeaderboardResponse.self)
    }

    func feed() async throws -> FeedResponse {
        try await request("feed", decode: FeedResponse.self)
    }

    func myFeed() async throws -> FeedResponse {
        try await request("feed/me", decode: FeedResponse.self)
    }

    func badges() async throws -> [Badge] {
        try await request("badges/me", decode: [Badge].self)
    }

    func shareCard(year: Int) async throws -> ShareCardResponse {
        struct Body: Encodable { let card_type: String; let year: Int }
        return try await request("share/card", method: "POST",
            body: Body(card_type: "year_recap", year: year), decode: ShareCardResponse.self)
    }
}

struct EmptyResponse: Decodable {}

/// Type-erasing wrapper so we can send any `Encodable` body.
struct AnyEncodable: Encodable {
    private let encodeFunc: (Encoder) throws -> Void
    init(_ wrapped: Encodable) { encodeFunc = wrapped.encode }
    func encode(to encoder: Encoder) throws { try encodeFunc(encoder) }
}
