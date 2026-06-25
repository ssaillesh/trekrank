import SwiftUI

extension Color {
    /// Build a Color from a 6-digit RGB hex string (e.g. "d4af37"). Used by the
    /// metallic badge palette so colours can be listed compactly like the web.
    static func hex(_ s: String) -> Color {
        let v = UInt64(s, radix: 16) ?? 0
        return Color(red: Double((v >> 16) & 0xff) / 255,
                     green: Double((v >> 8) & 0xff) / 255,
                     blue: Double(v & 0xff) / 255)
    }
}

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

/// Subtly glowing background used behind every screen.
///
/// The two neon blobs are static — deliberately NOT animated with
/// `.repeatForever`. A perpetual animation would force the GPU to re-render
/// these large blurs every frame on every screen, which pins the iOS
/// Simulator's GPU and overheats the Mac. Being static, they render once and
/// the compositor caches them, so the cost is paid a single time.
struct ScreenBackground: View {
    var body: some View {
        ZStack {
            TrekTheme.gradient.ignoresSafeArea()
            Circle().fill(TrekTheme.accent.opacity(0.18))
                .frame(width: 320).blur(radius: 60)
                .offset(x: -110, y: -280)
            Circle().fill(TrekTheme.accent2.opacity(0.18))
                .frame(width: 300).blur(radius: 60)
                .offset(x: 120, y: 340)
        }
        .ignoresSafeArea()
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

/// A metallic medal badge. Unlike the old design (a circular coin with an SF
/// Symbol inset), the medal *is the symbol itself*, metal-filled — exactly like
/// the web "badges 1.0" silhouette medals. The symbol's own vector outline is
/// filled with a conic metal sheen (gold/silver/bronze/copper/steel/emerald/
/// sapphire/platinum/amethyst), with a top gloss and a darker rim for relief.
struct BadgeMedallion: View {
    let badge: Badge
    var size: CGFloat = 64

    var body: some View {
        let metal = Self.metal(for: badge)
        // The silhouettes live in a 0–48 viewBox; scale to the requested size.
        let shape = BadgeSilhouette.named(Self.silhouette(badge))
            .outline.applying(CGAffineTransform(scaleX: size / 48, y: size / 48))
        ZStack {
            // Conic "struck metal" sheen filling the symbol shape.
            shape.fill(AngularGradient(
                colors: metal.stops, center: .center, angle: .degrees(215)))
            // Glossy top sheen, confined to the shape.
            shape.fill(LinearGradient(
                colors: [.white.opacity(0.45), .white.opacity(0)],
                startPoint: .top, endPoint: .center))
            // Darker rim gives the metal edge relief.
            shape.stroke(metal.rim.opacity(0.85),
                         style: StrokeStyle(lineWidth: max(0.6, size * 0.018),
                                            lineJoin: .round))
        }
        .frame(width: size, height: size)
        .shadow(color: .black.opacity(0.40), radius: size * 0.10, y: size * 0.06)
        .grayscale(badge.earned ? 0 : 1)
        .opacity(badge.earned ? 1 : 0.45)
    }

    struct Metal {
        let stops: [Color]   // conic ring of shades, light→dark→light
        let rim: Color       // dark edge / glyph color
    }

    // The 9 metals from the web medal system, as conic colour rings.
    static let metals: [String: Metal] = [
        "gold":     Metal(stops: ["7a5b12","ffe9a3","d4af37","fff6d5","c9a52f","7a5b12","ffe39a","d4af37","7a5b12"].map(Color.hex), rim: .hex("5c4310")),
        "silver":   Metal(stops: ["5f6b7a","f2f6fb","aeb9c8","ffffff","94a0b0","5f6b7a","e3e9f1","aeb9c8","5f6b7a"].map(Color.hex), rim: .hex("46505c")),
        "bronze":   Metal(stops: ["5a3413","eaa869","c87f3a","ffd9a8","a8682c","5a3413","df9e5e","c87f3a","5a3413"].map(Color.hex), rim: .hex("3f250d")),
        "copper":   Metal(stops: ["6e2c12","ff9e6b","d6603a","ffc8a6","b04a26","6e2c12","ef8a58","d6603a","6e2c12"].map(Color.hex), rim: .hex("4d1f0d")),
        "steel":    Metal(stops: ["363f4d","9fb1c6","5d6d82","cdd9e8","525f72","363f4d","8ea1b8","5d6d82","363f4d"].map(Color.hex), rim: .hex("252c36")),
        "emerald":  Metal(stops: ["0c5a42","79efc2","19a87c","caffee","138a66","0c5a42","6ae8b6","19a87c","0c5a42"].map(Color.hex), rim: .hex("083a2c")),
        "sapphire": Metal(stops: ["192a7a","8aa6ff","3f57cf","cdd9ff","314ac0","192a7a","7d9bff","3f57cf","192a7a"].map(Color.hex), rim: .hex("121d52")),
        "platinum": Metal(stops: ["7c8a9d","f4f8ff","c4d0e0","ffffff","b1bed2","7c8a9d","e7eef8","c4d0e0","7c8a9d"].map(Color.hex), rim: .hex("586271")),
        "amethyst": Metal(stops: ["4a1d73","d59bff","8a3fd4","f1d7ff","7a32c0","4a1d73","c98cff","8a3fd4","4a1d73"].map(Color.hex), rim: .hex("341452")),
    ]

    // Metal assignment per badge — prestige = gold/amethyst, distance = sapphire,
    // polar = platinum, transport = steel, cities = emerald, default by category.
    static func metal(for badge: Badge) -> Metal {
        let key: String
        switch badge.id {
        case "fifty_countries":                         key = "amethyst"
        case "twenty_five", "all_continents",
             "fifty_cities", "north_america":           key = "gold"
        case "fifty_k_km", "ten_k_km":                  key = "sapphire"
        case "ten_cities", "europe", "visited_eu",
             "visited_sa", "asia", "visited_as":        key = "emerald"
        case "first_flight", "train_lover",
             "road_warrior", "visited_na":              key = "steel"
        case "visited_an":                              key = "platinum"
        case "visited_oc", "weekend_warrior":           key = "copper"
        case "five_countries", "ten_countries",
             "first_trip", "visited_af":                key = "bronze"
        default:
            switch badge.category {
            case "transport": key = "steel"
            case "continent": key = "emerald"
            case "distance":  key = "sapphire"
            default:          key = "silver"
            }
        }
        return metals[key] ?? metals["silver"]!
    }

    // Silhouette per badge — the same vector symbols the web uses.
    static func silhouette(_ badge: Badge) -> String {
        switch badge.id {
        case "first_trip":       return "map"
        case "five_countries":   return "globe"
        case "ten_countries":    return "globe"
        case "twenty_five":      return "trophy"
        case "fifty_countries":  return "crown"
        case "ten_cities":       return "cityhop"
        case "fifty_cities":     return "cityhop"
        case "ten_k_km":         return "orbit"
        case "fifty_k_km":       return "orbit"
        case "north_america":    return "flag"
        case "europe":           return "flag"
        case "asia":             return "flag"
        case "first_flight":     return "plane"
        case "train_lover":      return "train"
        case "road_warrior":     return "compass"
        case "weekend_warrior":  return "backpack"
        case "photographer":     return "compass"
        case "visited_af":       return "compass"
        case "visited_as":       return "compass"
        case "visited_eu":       return "compass"
        case "visited_na":       return "compass"
        case "visited_sa":       return "compass"
        case "visited_oc":       return "downunder"
        case "visited_an":       return "polar"
        case "all_continents":   return "globe"
        default:
            switch badge.category {
            case "transport": return "plane"
            case "continent": return "compass"
            case "distance":  return "orbit"
            default:          return "trophy"
            }
        }
    }
}

// MARK: - Badge silhouettes (vector medal shapes)

/// A vector silhouette in the symbols' native 0–48 coordinate space, built from
/// the exact same path data the web uses (see `SIL` in webui/index.html). Stroked
/// elements are converted to fillable outlines so the whole medal can be filled
/// with one metal gradient.
struct BadgeSilhouette {
    struct Part { let path: Path; let stroke: CGFloat? }   // stroke == nil → fill
    let parts: [Part]

    /// Combined fillable outline (strokes flattened to outlines).
    var outline: Path {
        var p = Path()
        for part in parts {
            if let w = part.stroke {
                p.addPath(part.path.strokedPath(
                    StrokeStyle(lineWidth: w, lineCap: .round, lineJoin: .round)))
            } else {
                p.addPath(part.path)
            }
        }
        return p
    }

    // Builders mirroring the SVG primitives used by the web silhouettes.
    private static func pathP(_ d: String, _ stroke: CGFloat? = nil) -> Part {
        Part(path: SVGPath.parse(d), stroke: stroke)
    }
    private static func circle(_ cx: CGFloat, _ cy: CGFloat, _ r: CGFloat, _ stroke: CGFloat? = nil) -> Part {
        Part(path: Path(ellipseIn: CGRect(x: cx - r, y: cy - r, width: 2 * r, height: 2 * r)), stroke: stroke)
    }
    private static func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ r: CGFloat = 0, _ stroke: CGFloat? = nil) -> Part {
        Part(path: Path(roundedRect: CGRect(x: x, y: y, width: w, height: h), cornerRadius: r), stroke: stroke)
    }
    private static func ellipse(_ cx: CGFloat, _ cy: CGFloat, _ rx: CGFloat, _ ry: CGFloat, rotation deg: CGFloat = 0, _ stroke: CGFloat? = nil) -> Part {
        var p = Path(ellipseIn: CGRect(x: cx - rx, y: cy - ry, width: 2 * rx, height: 2 * ry))
        if deg != 0 {
            let t = CGAffineTransform(translationX: cx, y: cy)
                .rotated(by: deg * .pi / 180)
                .translatedBy(x: -cx, y: -cy)
            p = p.applying(t)
        }
        return Part(path: p, stroke: stroke)
    }

    static func named(_ name: String) -> BadgeSilhouette {
        switch name {
        case "plane":
            return BadgeSilhouette(parts: [pathP("M46 4 18 21 4 18 1 22 11 28 14 41 19 35 21 27Z")])
        case "globe":
            return BadgeSilhouette(parts: [
                circle(24, 24, 17, 3.2),
                pathP("M7 24h34", 2.4),
                ellipse(24, 24, 8, 17, 2.4)])
        case "trophy":
            return BadgeSilhouette(parts: [
                pathP("M14 8h20v6a10 10 0 0 1-20 0Z"),
                pathP("M14 9h-5a5 5 0 0 0 6 7M34 9h5a5 5 0 0 1-6 7", 3),
                rect(21, 23, 6, 8),
                rect(13, 31, 22, 5, 1),
                rect(16, 36, 16, 4, 1)])
        case "orbit":
            return BadgeSilhouette(parts: [
                circle(24, 24, 9),
                ellipse(24, 24, 20, 7, rotation: -25, 3.5)])
        case "train":
            return BadgeSilhouette(parts: [
                rect(10, 9, 28, 22, 5),
                circle(17, 35, 3),
                circle(31, 35, 3),
                pathP("M8 41h32", 3)])
        case "cityhop":
            return BadgeSilhouette(parts: [
                rect(6, 22, 9, 20),
                rect(18, 13, 11, 29),
                rect(32, 26, 9, 16),
                rect(22.5, 5, 2, 9)])
        case "polar":
            return BadgeSilhouette(parts: [
                pathP("M3 41 17 16 26 31 32 21 45 41Z"),
                circle(36, 12, 5)])
        case "downunder":
            return BadgeSilhouette(parts: [
                pathP("M11 6C28 9 39 24 41 43 31 39 22 30 18 19 16 14 13 10 11 6Z")])
        case "backpack":
            return BadgeSilhouette(parts: [
                rect(12, 12, 24, 30, 8),
                pathP("M19 13c0-6 10-6 10 0", 3.5)])
        case "crown":
            return BadgeSilhouette(parts: [
                pathP("M7 36 5 13 16.5 22 24 7 31.5 22 43 13 41 36Z"),
                rect(7, 37, 34, 5, 1)])
        case "compass":
            return BadgeSilhouette(parts: [
                circle(24, 24, 17, 4),
                pathP("M24 9 28 24 24 39 20 24Z"),
                pathP("M9 24 24 20 39 24 24 28Z")])
        case "map":
            return BadgeSilhouette(parts: [pathP("M6 12 18 8 30 12 42 8V36L30 40 18 36 6 40Z")])
        default: // "trophy" fallback
            return BadgeSilhouette(parts: [
                pathP("M14 8h20v6a10 10 0 0 1-20 0Z"),
                rect(21, 23, 6, 8),
                rect(13, 31, 22, 5, 1),
                rect(16, 36, 16, 4, 1)])
        }
    }
}

/// Minimal SVG-`d` parser → SwiftUI `Path`, just enough for the badge
/// silhouettes: M L H V C and circular arcs (A), absolute and relative, with
/// implicit command repetition. Coordinates are in the 0–48 viewBox space.
enum SVGPath {
    private struct Scan {
        let c: [Character]; var i = 0
        init(_ s: String) { c = Array(s) }
        mutating func skip() { while i < c.count, c[i] == " " || c[i] == "," || c[i] == "\n" || c[i] == "\t" { i += 1 } }
        var peekLetter: Bool { var j = i; while j < c.count, c[j] == " " || c[j] == "," || c[j] == "\n" || c[j] == "\t" { j += 1 }; return j < c.count && c[j].isLetter }
        var peekNumber: Bool { var j = i; while j < c.count, c[j] == " " || c[j] == "," || c[j] == "\n" || c[j] == "\t" { j += 1 }; guard j < c.count else { return false }; let ch = c[j]; return ch.isNumber || ch == "-" || ch == "+" || ch == "." }
        mutating func letter() -> Character { skip(); let ch = c[i]; i += 1; return ch }
        mutating func number() -> CGFloat {
            skip(); var s = ""
            if i < c.count, c[i] == "-" || c[i] == "+" { s.append(c[i]); i += 1 }
            while i < c.count, c[i].isNumber || c[i] == "." { s.append(c[i]); i += 1 }
            return CGFloat(Double(s) ?? 0)
        }
    }

    static func parse(_ d: String) -> Path {
        var sc = Scan(d)
        var path = Path()
        var cur = CGPoint.zero
        var startPt = CGPoint.zero
        var cmd: Character = " "
        func point(_ rel: Bool) -> CGPoint {
            let x = sc.number(), y = sc.number()
            return rel ? CGPoint(x: cur.x + x, y: cur.y + y) : CGPoint(x: x, y: y)
        }
        while sc.peekLetter || sc.peekNumber {
            if sc.peekLetter { cmd = sc.letter() }
            else if cmd == "M" { cmd = "L" } else if cmd == "m" { cmd = "l" }   // implicit lineto
            let rel = cmd.isLowercase
            switch Character(cmd.lowercased()) {
            case "m":
                let p = point(rel); path.move(to: p); cur = p; startPt = p
            case "l":
                let p = point(rel); path.addLine(to: p); cur = p
            case "h":
                let x = sc.number(); let p = CGPoint(x: rel ? cur.x + x : x, y: cur.y)
                path.addLine(to: p); cur = p
            case "v":
                let y = sc.number(); let p = CGPoint(x: cur.x, y: rel ? cur.y + y : y)
                path.addLine(to: p); cur = p
            case "c":
                let c1 = point(rel), c2 = point(rel), e = point(rel)
                path.addCurve(to: e, control1: c1, control2: c2); cur = e
            case "a":
                let rx = sc.number(), ry = sc.number(); _ = sc.number()   // x-rotation (0)
                let large = sc.number() != 0, sweep = sc.number() != 0
                let e = point(rel)
                arc(&path, from: cur, to: e, r: (rx + ry) / 2, largeArc: large, sweep: sweep); cur = e
            case "z":
                path.closeSubpath(); cur = startPt
                if !sc.peekLetter { return path }   // guard against trailing junk
            default:
                return path
            }
        }
        return path
    }

    /// Circular arc (rx == ry) from `p0` to `p1`, approximated with cubic beziers.
    private static func arc(_ path: inout Path, from p0: CGPoint, to p1: CGPoint, r: CGFloat, largeArc: Bool, sweep: Bool) {
        let half = hypot(p0.x - p1.x, p0.y - p1.y) / 2
        let radius = max(r, half)                     // enlarge if the chord won't fit
        let mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2
        let x1 = (p0.x - p1.x) / 2, y1 = (p0.y - p1.y) / 2
        let denom = x1 * x1 + y1 * y1
        var coef = sqrt(max(0, radius * radius - denom) / max(denom, 1e-9))
        if largeArc == sweep { coef = -coef }
        let cx = coef * y1 + mx, cy = -coef * x1 + my
        let a0 = atan2(p0.y - cy, p0.x - cx)
        let a1 = atan2(p1.y - cy, p1.x - cx)
        var delta = a1 - a0
        if sweep && delta < 0 { delta += 2 * .pi }
        if !sweep && delta > 0 { delta -= 2 * .pi }
        let segs = max(1, Int(ceil(abs(delta) / (.pi / 2))))
        let step = delta / CGFloat(segs)
        var ang = a0
        for _ in 0..<segs {
            let next = ang + step
            let t = tan(step / 4)
            let alpha = sin(step) * (sqrt(4 + 3 * t * t) - 1) / 3
            let pEnd = CGPoint(x: cx + radius * cos(next), y: cy + radius * sin(next))
            let cs = CGPoint(x: cx + radius * cos(ang) - alpha * radius * sin(ang),
                             y: cy + radius * sin(ang) + alpha * radius * cos(ang))
            let ce = CGPoint(x: pEnd.x + alpha * radius * sin(next),
                             y: pEnd.y - alpha * radius * cos(next))
            path.addCurve(to: pEnd, control1: cs, control2: ce)
            ang = next
        }
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
