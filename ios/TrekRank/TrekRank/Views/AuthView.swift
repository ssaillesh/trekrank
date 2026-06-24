import SwiftUI

struct AuthView: View {
    @EnvironmentObject var session: SessionStore
    @State private var isRegister = false
    @State private var email = ""
    @State private var username = ""
    @State private var displayName = ""
    @State private var password = ""
    @State private var showResetSheet = false

    var body: some View {
        ZStack {
            ScreenBackground()
            VStack(spacing: 20) {
                Spacer()
                Image(systemName: "globe.americas.fill")
                    .font(.system(size: 72)).foregroundStyle(TrekTheme.accent)
                    .shadow(color: TrekTheme.accent.opacity(0.6), radius: 20)
                Text("TrekRank").font(.largeTitle.bold()).foregroundStyle(.white)
                Text("Log trips. Climb the ranks.").foregroundStyle(.white.opacity(0.7))

                GlassCard {
                    VStack(spacing: 12) {
                        field("Email", text: $email, keyboard: .emailAddress)
                        if isRegister {
                            field("Username", text: $username)
                            field("Display name", text: $displayName)
                        }
                        secureField("Password", text: $password)
                    }
                }
                .padding(.top, 8)

                if let err = session.errorMessage {
                    Text(err).font(.caption).foregroundStyle(.red).multilineTextAlignment(.center)
                }

                Button(action: submit) {
                    HStack {
                        if session.isLoading { ProgressView().tint(.black) }
                        Text(isRegister ? "Create account" : "Log in")
                    }
                }
                .buttonStyle(NeonButtonStyle())
                .disabled(session.isLoading)

                Button(isRegister ? "Have an account? Log in" : "New here? Create an account") {
                    withAnimation { isRegister.toggle(); session.errorMessage = nil }
                }
                .font(.footnote).foregroundStyle(.white.opacity(0.8))

                if !isRegister {
                    Button("Forgot password?") {
                        session.errorMessage = nil
                        showResetSheet = true
                    }
                    .font(.footnote).foregroundStyle(TrekTheme.accent)
                }
                Spacer()
            }
            .padding(28)
        }
        .sheet(isPresented: $showResetSheet) {
            PasswordResetView(prefillEmail: email)
                .environmentObject(session)
        }
    }

    private func submit() {
        Task {
            if isRegister {
                await session.register(email: email, username: username,
                                       displayName: displayName.isEmpty ? username : displayName,
                                       password: password)
            } else {
                await session.login(email: email, password: password)
            }
        }
    }

    private func field(_ label: String, text: Binding<String>, keyboard: UIKeyboardType = .default) -> some View {
        TextField(label, text: text)
            .textInputAutocapitalization(.never).autocorrectionDisabled()
            .keyboardType(keyboard)
            .padding().background(.white.opacity(0.1))
            .foregroundStyle(.white).clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func secureField(_ label: String, text: Binding<String>) -> some View {
        SecureField(label, text: text)
            .padding().background(.white.opacity(0.1))
            .foregroundStyle(.white).clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

/// Two-step password reset: request a code by email, then enter the code +
/// a new password. Works without any website — the code arrives by email.
struct PasswordResetView: View {
    @EnvironmentObject var session: SessionStore
    @Environment(\.dismiss) private var dismiss

    let prefillEmail: String
    @State private var email = ""
    @State private var codeSent = false
    @State private var infoMessage: String?
    @State private var resetCode = ""
    @State private var newPassword = ""

    var body: some View {
        NavigationStack {
            Form {
                if !codeSent {
                    Section("Reset your password") {
                        TextField("Email", text: $email)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .keyboardType(.emailAddress)
                    }
                    Section {
                        Button {
                            Task {
                                if let msg = await session.forgotPassword(email: email) {
                                    infoMessage = msg
                                    withAnimation { codeSent = true }
                                }
                            }
                        } label: {
                            HStack {
                                if session.isLoading { ProgressView() }
                                Text("Send reset code")
                            }
                        }
                        .disabled(email.isEmpty || session.isLoading)
                    } footer: {
                        Text("We'll email you a reset code if an account exists for that address.")
                    }
                } else {
                    Section {
                        if let info = infoMessage {
                            Text(info).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    Section("Enter the code from your email") {
                        TextField("Reset code", text: $resetCode)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                        SecureField("New password (min 6 chars)", text: $newPassword)
                    }
                    Section {
                        Button {
                            Task {
                                await session.resetPassword(token: resetCode.trimmingCharacters(in: .whitespacesAndNewlines),
                                                            newPassword: newPassword)
                                if session.isAuthenticated { dismiss() }
                            }
                        } label: {
                            HStack {
                                if session.isLoading { ProgressView() }
                                Text("Reset password & sign in")
                            }
                        }
                        .disabled(resetCode.isEmpty || newPassword.count < 6 || session.isLoading)
                    }
                }

                if let err = session.errorMessage {
                    Section { Text(err).font(.footnote).foregroundStyle(.red) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(ScreenBackground())
            .navigationTitle("Forgot password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { session.errorMessage = nil; dismiss() }
                }
            }
            .onAppear { if email.isEmpty { email = prefillEmail } }
        }
    }
}
