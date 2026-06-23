import SwiftUI

extension Color {
    // 背景层
    static let bgRice = Color(red: 0.96, green: 0.95, blue: 0.91)
    static let bgCard = Color.white
    static let bgElevated = Color(red: 0.98, green: 0.98, blue: 0.97)

    // 文字层
    static let ink = Color(red: 0.11, green: 0.11, blue: 0.12)
    static let inkSecondary = Color(red: 0.24, green: 0.24, blue: 0.27)
    static let inkTertiary = Color(red: 0.56, green: 0.56, blue: 0.57)

    // 主点缀 - 朱砂
    static let vermilion = Color(red: 0.75, green: 0.22, blue: 0.17)
    static let vermilionSoft = Color(red: 0.98, green: 0.92, blue: 0.91)

    // 次点缀 - 青铜金
    static let bronze = Color(red: 0.55, green: 0.41, blue: 0.08)
    static let bronzeDeep = Color(red: 0.36, green: 0.29, blue: 0.12)
    static let bronzeSoft = Color(red: 0.96, green: 0.94, blue: 0.88)

    // 完成态 - 玉色
    static let jade = Color(red: 0.35, green: 0.49, blue: 0.43)
    static let jadeSoft = Color(red: 0.91, green: 0.95, blue: 0.93)

    // 分隔线 / 状态
    static let line = Color(red: 0.91, green: 0.89, blue: 0.85)
    static let success = Color(red: 0.20, green: 0.78, blue: 0.35)
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
