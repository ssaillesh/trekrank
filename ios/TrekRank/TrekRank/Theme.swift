import SwiftUI

/// Shared dark + neon design system: colors, backgrounds, and reusable
/// "frosted glass" building blocks used across every screen.
enum TrekTheme {
    static let accent = Color(red: 0.37, green: 0.92, blue: 0.83)   // teal neon
    static let accent2 = Color(red: 0.45, green: 0.55, blue: 1.0)   // indigo glow
    static let deep = Color(red: 0.09, green: 0.13, blue: 0.22)
    static let bg0 = Color(red: 0.04, green: 0.06, blue: 0.11)
    static let bg1 = Color(red: 0.07, green: 0.10, blue: 0.18)

    static let gradient = LinearGradient(
        colors: [bg1, bg0], startPoint: .top, endPoint: .bottom)
}

/// Animated, subtly glowing background used behind every screen.
struct ScreenBackground: View {
    @State private var drift = false
    var body: some View {
        ZStack {
            TrekTheme.gradient.ignoresSafeArea()
            // Two soft neon blobs that slowly drift for a "dynamic" feel.
            Circle().fill(TrekTheme.accent.opacity(0.18))
                .frame(width: 320).blur(radius: 90)
                .offset(x: drift ? -120 : -90, y: drift ? -260 : -300)
            Circle().fill(TrekTheme.accent2.opacity(0.18))
                .frame(width: 300).blur(radius: 90)
                .offset(x: drift ? 130 : 100, y: drift ? 320 : 360)
        }
        .ignoresSafeArea()
        .onAppear {
            withAnimation(.easeInOut(duration: 9).repeatForever(autoreverses: true)) {
                drift.toggle()
            }
        }
    }
}

/// Frosted-glass card container.
struct GlassCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(16)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(.white.opacity(0.10), lineWidth: 1))
            .shadow(color: .black.opacity(0.25), radius: 12, y: 6)
    }
}

extension View {
    /// Standard screen scaffold: dark animated background + content.
    func trekScreen() -> some View {
        self.background(ScreenBackground()).scrollContentBackground(.hidden)
    }
}

/// A neon primary button style.
struct NeonButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity).padding(.vertical, 14)
            .background(
                LinearGradient(colors: [TrekTheme.accent, TrekTheme.accent.opacity(0.8)],
                               startPoint: .leading, endPoint: .trailing),
                in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .foregroundStyle(.black)
            .shadow(color: TrekTheme.accent.opacity(0.5), radius: configuration.isPressed ? 4 : 12, y: 4)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

/// A number that counts up when it appears — adds life to stats.
struct CountUpText: View {
    let value: Double
    var suffix: String = ""
    var format: (Double) -> String = { String(Int($0)) }

    @State private var shown: Double = 0
    var body: some View {
        Text(format(shown) + suffix)
            .monospacedDigit()
            .onAppear {
                withAnimation(.easeOut(duration: 0.8)) { shown = value }
            }
            .onChange(of: value) { _, new in
                withAnimation(.easeOut(duration: 0.6)) { shown = new }
            }
    }
}
