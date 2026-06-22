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

    enum CodingKeys: String, CodingKey {
        case id, username, email, bio
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case homeCity = "home_city"
        case homeCountry = "home_country"
        case totalCountries = "total_countries"
        case totalCities = "total_cities"
        case totalKm = "total_km"
        case totalTrips = "total_trips"
        case currentStreak = "current_streak"
        case longestStreak = "longest_streak"
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
    }
}

// MARK: - Map

struct MapCountry: Codable, Identifiable {
    var id: String { code }
    let code: String
    let name: String
    let visits: Int
}

struct MapCity: Codable, Identifiable {
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

struct FeedItem: Codable, Identifiable {
    let id: String
    let eventType: String
    let user: LeaderboardUser
    let trip: FeedTrip?
    let badge: FeedBadge?
    let photoUrl: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, user, trip, badge
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
    var earned: Bool
    var earnedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, name, description, category, earned
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
