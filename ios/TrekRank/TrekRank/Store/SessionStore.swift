import Foundation
import SwiftUI

/// Holds auth state + the current user's profile. Persists tokens in UserDefaults
/// (a Keychain wrapper would be the production choice).
@MainActor
final class SessionStore: ObservableObject {
    @Published var user: AuthUser?
    @Published var profile: UserProfile?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let tokenKey = "trekrank.accessToken"
    private let refreshKey = "trekrank.refreshToken"
    private let userKey = "trekrank.user"

    var isAuthenticated: Bool { user != nil }

    init() {
        if let token = UserDefaults.standard.string(forKey: tokenKey),
           let data = UserDefaults.standard.data(forKey: userKey),
           let saved = try? JSONDecoder().decode(AuthUser.self, from: data) {
            self.user = saved
            Task { await APIClient.shared.setToken(token) ; await refreshProfile() }
        }
    }

    func register(email: String, username: String, displayName: String, password: String) async {
        await run {
            let resp = try await APIClient.shared.register(
                email: email, username: username, displayName: displayName, password: password)
            try await self.apply(resp)
        }
    }

    func login(email: String, password: String) async {
        await run {
            let resp = try await APIClient.shared.login(email: email, password: password)
            try await self.apply(resp)
        }
    }

    /// Requests a password reset. Returns the user-facing message. In production
    /// the reset link is emailed; the returned token (dev only) is ignored here.
    func forgotPassword(email: String) async -> String? {
        var message: String?
        await run {
            let resp = try await APIClient.shared.forgotPassword(email: email)
            message = resp.message
        }
        return message
    }

    /// Completes a reset with the emailed token and logs the user in.
    func resetPassword(token: String, newPassword: String) async {
        await run {
            let resp = try await APIClient.shared.resetPassword(token: token, newPassword: newPassword)
            try await self.apply(resp)
        }
    }

    /// Updates the account email. Returns true on success.
    func updateEmail(_ email: String) async -> Bool {
        var ok = false
        await run {
            self.profile = try await APIClient.shared.updateProfile(email: email)
            ok = true
        }
        return ok
    }

    /// Updates display name / bio / home location.
    func updateProfile(displayName: String? = nil, bio: String? = nil,
                       homeCity: String? = nil, homeCountry: String? = nil) async -> Bool {
        var ok = false
        await run {
            self.profile = try await APIClient.shared.updateProfile(
                displayName: displayName, bio: bio, homeCity: homeCity, homeCountry: homeCountry)
            ok = true
        }
        return ok
    }

    /// Changes the password (requires the current one). Returns true on success.
    func changePassword(current: String, newPassword: String) async -> Bool {
        var ok = false
        await run {
            let resp = try await APIClient.shared.changePassword(current: current, newPassword: newPassword)
            try await self.apply(resp)
            ok = true
        }
        return ok
    }

    /// Permanently deletes the account and all its data, then signs out.
    func deleteAccount() async {
        await run {
            try await APIClient.shared.deleteAccount()
        }
        if errorMessage == nil { logout() }
    }

    func logout() {
        UserDefaults.standard.removeObject(forKey: tokenKey)
        UserDefaults.standard.removeObject(forKey: refreshKey)
        UserDefaults.standard.removeObject(forKey: userKey)
        user = nil
        profile = nil
        Task { await APIClient.shared.setToken(nil) }
    }

    func refreshProfile() async {
        if let p = try? await APIClient.shared.me() { self.profile = p }
    }

    /// Pin up to 3 badges to show off on the profile. Updates `profile` on success.
    func setFeaturedBadges(_ ids: [String]) async {
        if let p = try? await APIClient.shared.setFeaturedBadges(ids) { self.profile = p }
    }

    private func apply(_ resp: TokenResponse) async throws {
        UserDefaults.standard.set(resp.accessToken, forKey: tokenKey)
        UserDefaults.standard.set(resp.refreshToken, forKey: refreshKey)
        if let data = try? JSONEncoder().encode(resp.user) {
            UserDefaults.standard.set(data, forKey: userKey)
        }
        await APIClient.shared.setToken(resp.accessToken)
        self.user = resp.user
        await refreshProfile()
    }

    private func run(_ work: @escaping () async throws -> Void) async {
        isLoading = true; errorMessage = nil
        do { try await work() }
        catch { errorMessage = (error as? APIError)?.errorDescription ?? error.localizedDescription }
        isLoading = false
    }
}
