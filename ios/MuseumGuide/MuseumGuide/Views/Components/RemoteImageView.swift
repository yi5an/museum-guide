import Kingfisher
import SwiftUI

/// 远程图片视图（带缓存）。
///
/// 使用 Kingfisher 提供两级缓存（内存 LRU + 磁盘）：
/// - 滚动列表时图片不重复下载，平滑无闪烁
/// - 离线时仍能显示已缓存的图片
/// - 自动处理下载失败重试与占位图
struct RemoteImageView: View {
    let url: String?
    var height: CGFloat = 140

    var body: some View {
        if let urlString = url, let url = URL(string: urlString) {
            KFImage(url)
                .placeholder { placeholder.overlay { ProgressView().tint(.white) } }
                .onFailureView { fallback }
                .resizable()
                .aspectRatio(contentMode: .fill)
                .frame(height: height)
                .clipped()
        } else {
            fallback
        }
    }

    private var placeholder: some View {
        LinearGradient(colors: [.bronzeDeep, Color.bronze],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
            .frame(height: height)
    }

    private var fallback: some View {
        LinearGradient(colors: [.bronzeDeep, Color.bronze],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
            .frame(height: height)
            .overlay {
                Image(systemName: "building.columns.fill")
                    .font(.system(size: 40)).opacity(0.2).foregroundStyle(.white)
            }
    }
}
