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
