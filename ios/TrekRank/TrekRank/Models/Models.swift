import Foundation

// MARK: - Auth

struct AuthUser: Codable, Identifiable {
    let id: String
    let username: String
    let displayName: String
    var isNewUser: Bool? = false

    enum CodingKeys: String, CodingKey {
        case id, username
        case displayName = "display_name"
        case isNewUser = "is_new_user"
    }
}

struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let user: AuthUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

struct ForgotPasswordResponse: Codable {
    let message: String
    /// Present only when the backend has no email service configured (dev). In
    /// production this is nil and the reset token is delivered by email.
    let resetToken: String?

    enum CodingKeys: String, CodingKey {
        case message
        case resetToken = "reset_token"
    }
}

// MARK: - Profile / stats

struct UserProfile: Codable, Identifiable {
    let id: String
    let username: String
    let displayName: String
    var avatarUrl: String?
    var bio: String?
    var homeCity: String?
    var homeCountry: String?
    var email: String?
    var totalCountries: Int
    var totalCities: Int
    var totalKm: Double
    var totalTrips: Int
    var currentStreak: Int
    var longestStreak: Int
    /// Up to 3 badge ids the user pinned to show off, in display order.
    var featuredBadges: [String] = []

    enum CodingKeys: String, CodingKey {
        case id, username, email, bio
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case homeCity = "home_city"
        case homeCountry = "home_country"
        case featuredBadges = "featured_badges"
        case totalCountries = "total_countries"
        case totalCities = "total_cities"
        case totalKm = "total_km"
        case totalTrips = "total_trips"
        case currentStreak = "current_streak"
        case longestStreak = "longest_streak"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        username = try c.decode(String.self, forKey: .username)
        displayName = try c.decode(String.self, forKey: .displayName)
        avatarUrl = try c.decodeIfPresent(String.self, forKey: .avatarUrl)
        bio = try c.decodeIfPresent(String.self, forKey: .bio)
        homeCity = try c.decodeIfPresent(String.self, forKey: .homeCity)
        homeCountry = try c.decodeIfPresent(String.self, forKey: .homeCountry)
        email = try c.decodeIfPresent(String.self, forKey: .email)
        featuredBadges = try c.decodeIfPresent([String].self, forKey: .featuredBadges) ?? []
        totalCountries = try c.decode(Int.self, forKey: .totalCountries)
        totalCities = try c.decode(Int.self, forKey: .totalCities)
        totalKm = try c.decode(Double.self, forKey: .totalKm)
        totalTrips = try c.decode(Int.self, forKey: .totalTrips)
        currentStreak = try c.decode(Int.self, forKey: .currentStreak)
        longestStreak = try c.decode(Int.self, forKey: .longestStreak)
    }
}

struct UserStats: Codable {
    let totalCountries: Int
    let totalCities: Int
    let totalKm: Double
    let totalTrips: Int
    let currentStreak: Int
    let longestStreak: Int
    let continentsVisited: [String]
    let transportBreakdown: [String: Int]
    let yearStats: [String: [String: Double]]

    enum CodingKeys: String, CodingKey {
        case totalCountries = "total_countries"
        case totalCities = "total_cities"
        case totalKm = "total_km"
        case totalTrips = "total_trips"
        case currentStreak = "current_streak"
        case longestStreak = "longest_streak"
        case continentsVisited = "continents_visited"
        case transportBreakdown = "transport_breakdown"
        case yearStats = "year_stats"
    }
}

// MARK: - Trips

struct Trip: Codable, Identifiable {
    let id: String
    var title: String?
    var transportMode: String?
    var originCity: String?
    var originCountry: String?
    var destCity: String
    var destCountry: String
    var startDate: String
    var endDate: String?
    var distanceKm: Double?
    var status: String

    enum CodingKeys: String, CodingKey {
        case id, title, status
        case transportMode = "transport_mode"
        case originCity = "origin_city"
        case originCountry = "origin_country"
        case destCity = "dest_city"
        case destCountry = "dest_country"
        case startDate = "start_date"
        case endDate = "end_date"
        case distanceKm = "distance_km"
    }
}

struct TripList: Codable {
    let items: [Trip]
    let nextCursor: String?

    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}

struct CreateTripBody: Encodable {
    var title: String?
    var originCity: String?
    var originCountry: String?
    var destCity: String
    var destCountry: String
    var transportMode: String?
    var startDate: String
    var endDate: String?
    var notes: String?
    var isPublic: Bool = true
    // Resolved on-device (CLGeocoder) so the server skips its slow geocoding.
    var originLat: Double? = nil
    var originLng: Double? = nil
    var destLat: Double? = nil
    var destLng: Double? = nil
    var distanceKm: Double? = nil   // actual recorded distance (overrides server calc)

    enum CodingKeys: String, CodingKey {
        case title, notes
        case originCity = "origin_city"
        case originCountry = "origin_country"
        case destCity = "dest_city"
        case destCountry = "dest_country"
        case transportMode = "transport_mode"
        case startDate = "start_date"
        case endDate = "end_date"
        case isPublic = "is_public"
        case originLat = "origin_lat"
        case originLng = "origin_lng"
        case destLat = "dest_lat"
        case destLng = "dest_lng"
        case distanceKm = "distance_km"
    }
}

// MARK: - Map

struct MapCountry: Codable, Identifiable {
    var id: String { code }
    let code: String
    let name: String
    let visits: Int
}

struct MapCity: Codable, Identifiable, Hashable {
    var id: String { "\(name)-\(countryCode)" }
    let name: String
    let countryCode: String
    let lat: Double?
    let lng: Double?
    let visits: Int

    enum CodingKeys: String, CodingKey {
        case name, lat, lng, visits
        case countryCode = "country_code"
    }
}

struct UserMap: Codable {
    let countries: [MapCountry]
    let cities: [MapCity]
}

// MARK: - Leaderboard

struct LeaderboardUser: Codable {
    let id: String
    let username: String
    let displayName: String
    var avatarUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, username
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
    }
}

struct LeaderboardEntry: Codable, Identifiable {
    var id: Int { rank }
    let rank: Int
    let user: LeaderboardUser
    let value: Double
    let trend: String
}

struct LeaderboardResponse: Codable {
    let metric: String
    let period: String
    let rankings: [LeaderboardEntry]
    let myRank: Int?

    enum CodingKeys: String, CodingKey {
        case metric, period, rankings
        case myRank = "my_rank"
    }
}

// MARK: - Feed

struct FeedTrip: Codable {
    let id: String
    let title: String?
    let destCity: String
    let destCountry: String
    let distanceKm: Double?

    enum CodingKeys: String, CodingKey {
        case id, title
        case destCity = "dest_city"
        case destCountry = "dest_country"
        case distanceKm = "distance_km"
    }
}

struct FeedBadge: Codable {
    let id: String
    let name: String
    let iconUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, name
        case iconUrl = "icon_url"
    }
}

struct FeedRecommendation: Codable {
    let text: String
    let city: String?
    let country: String?
}

struct FollowStatus: Codable {
    let isFollowing: Bool
    let isSelf: Bool
    let followers: Int
    let following: Int

    enum CodingKeys: String, CodingKey {
        case isFollowing = "is_following"
        case isSelf = "is_self"
        case followers, following
    }
}

struct FeedItem: Codable, Identifiable {
    let id: String
    let eventType: String
    let user: LeaderboardUser
    let trip: FeedTrip?
    let badge: FeedBadge?
    let recommendation: FeedRecommendation?
    let photoUrl: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, user, trip, badge, recommendation
        case eventType = "event_type"
        case photoUrl = "photo_url"
        case createdAt = "created_at"
    }
}

struct FeedResponse: Codable {
    let items: [FeedItem]
    let nextCursor: String?

    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}

// MARK: - Badges

struct Badge: Codable, Identifiable {
    let id: String
    let name: String
    let description: String
    let category: String
    let emoji: String?
    var earned: Bool
    var earnedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, description, category, emoji, earned
        case earnedAt = "earned_at"
    }
}

// MARK: - Share

struct ShareCardResponse: Codable {
    let imageUrl: String
    let expiresAt: String

    enum CodingKeys: String, CodingKey {
        case imageUrl = "image_url"
        case expiresAt = "expires_at"
    }
}
