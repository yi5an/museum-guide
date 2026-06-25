import SwiftUI

// ShapeStyle 扩展：让 .foregroundStyle(.vermilion) / .background(.bgCard) / .fill(.line) 都能用点语法
extension ShapeStyle where Self == Color {
    static var bgRice: Color { Color(red: 0.96, green: 0.95, blue: 0.91) }
    static var bgCard: Color { .white }
    static var bgElevated: Color { Color(red: 0.98, green: 0.98, blue: 0.97) }
    static var ink: Color { Color(red: 0.11, green: 0.11, blue: 0.12) }
    static var inkPrimary: Color { Color(red: 0.11, green: 0.11, blue: 0.12) }
    static var inkSecondary: Color { Color(red: 0.24, green: 0.24, blue: 0.27) }
    static var inkTertiary: Color { Color(red: 0.56, green: 0.56, blue: 0.57) }
    static var vermilion: Color { Color(red: 0.75, green: 0.22, blue: 0.17) }
    static var vermilionSoft: Color { Color(red: 0.98, green: 0.92, blue: 0.91) }
    static var bronze: Color { Color(red: 0.55, green: 0.41, blue: 0.08) }
    static var bronzeDeep: Color { Color(red: 0.36, green: 0.29, blue: 0.12) }
    static var bronzeSoft: Color { Color(red: 0.96, green: 0.94, blue: 0.88) }
    static var jade: Color { Color(red: 0.35, green: 0.49, blue: 0.43) }
    static var jadeSoft: Color { Color(red: 0.91, green: 0.95, blue: 0.93) }
    static var line: Color { Color(red: 0.91, green: 0.89, blue: 0.85) }
    static var success: Color { Color(red: 0.20, green: 0.78, blue: 0.35) }
}

// Color 扩展：用于 .tint() / Canvas 等需要显式 Color 类型的场景
extension Color {
    static let bgColor = Color(red: 0.96, green: 0.95, blue: 0.91)  // 避免命名冲突，用 bgColor
}

extension Font {
    static let titleLarge = Font.system(size: 30, weight: .bold)
    static let titleMedium = Font.system(size: 22, weight: .bold)
    static let titleSection = Font.system(size: 20, weight: .bold)
    static let bodyEmphasis = Font.system(size: 17, weight: .semibold)
    static let body = Font.system(size: 14, weight: .regular)
    static let narrationBody = Font.system(size: 14, weight: .regular)
    static let caption = Font.system(size: 12, weight: .regular)
    static let microTag = Font.system(size: 10, weight: .medium)
    static let sectionHeading = Font.system(size: 13, weight: .bold)
}

extension CGFloat {
    static let spacing8: CGFloat = 8
    static let spacing12: CGFloat = 12
    static let spacing16: CGFloat = 16
    static let spacing20: CGFloat = 20
    static let spacing24: CGFloat = 24

    static let radiusSmall: CGFloat = 12
    static let radiusMedium: CGFloat = 14
    static let radiusLarge: CGFloat = 20
}
