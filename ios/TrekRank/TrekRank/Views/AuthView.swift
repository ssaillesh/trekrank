import SwiftUI

struct AuthView: View {
    @EnvironmentObject var session: SessionStore
    @State private var isRegister = false
    @State private var email = ""
    @State private var username = ""
    @State private var displayName = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            LinearGradient(colors: [TrekTheme.deep, .black],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
            VStack(spacing: 20) {
                Spacer()
                Image(systemName: "globe.americas.fill")
                    .font(.system(size: 72)).foregroundStyle(TrekTheme.accent)
                Text("TrekRank").font(.largeTitle.bold()).foregroundStyle(.white)
                Text("Log trips. Climb the ranks.").foregroundStyle(.white.opacity(0.7))

                VStack(spacing: 12) {
                    field("Email", text: $email, keyboard: .emailAddress)
                    if isRegister {
                        field("Username", text: $username)
                        field("Display name", text: $displayName)
                    }
                    secureField("Password", text: $password)
                }
                .padding(.top, 8)

                if let err = session.errorMessage {
                    Text(err).font(.caption).foregroundStyle(.red).multilineTextAlignment(.center)
                }

                Button(action: submit) {
                    HStack {
                        if session.isLoading { ProgressView().tint(.black) }
                        Text(isRegister ? "Create account" : "Log in").bold()
                    }
                    .frame(maxWidth: .infinity).padding()
                    .background(TrekTheme.accent).foregroundStyle(.black)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .disabled(session.isLoading)

                Button(isRegister ? "Have an account? Log in" : "New here? Create an account") {
                    withAnimation { isRegister.toggle(); session.errorMessage = nil }
                }
                .font(.footnote).foregroundStyle(.white.opacity(0.8))
                Spacer()
            }
            .padding(28)
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
