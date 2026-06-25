import SwiftUI

/// 远程图片视图。
/// 使用独立 URLSession + .reloadIgnoringLocalCacheData，避免 AsyncImage 缓存
/// 旧的失败结果或旧版本图片，确保每次启动都拉取最新图片。
struct RemoteImageView: View {
    let url: String?
    var height: CGFloat = 140

    var body: some View {
        if let urlString = url, let url = URL(string: urlString) {
            NoCacheAsyncImage(url: url) { phase in
                switch phase {
                case .loaded(let image):
                    image.resizable().aspectRatio(contentMode: .fill)
                case .failed:
                    fallback
                default:
                    fallback.overlay { ProgressView().tint(.white) }
                }
            }
            .frame(height: height)
            .clipped()
        } else {
            fallback
        }
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

/// 绕过 URLCache 的轻量异步图片加载器。
private struct NoCacheAsyncImage<Content: View>: View {
    let url: URL
    let content: (LoadPhase) -> Content
    @State private var phase: LoadPhase = .loading

    enum LoadPhase { case loading, loaded(Image), failed }

    var body: some View {
        content(phase)
            .task(id: url) { await load() }
    }

    @MainActor
    private func load() async {
        phase = .loading
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("MuseumGuide/1.0", forHTTPHeaderField: "User-Agent")
        do {
            let (data, resp) = try await URLSession.shared.data(for: request)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200,
                  let uiImage = UIImage(data: data) else {
                phase = .failed
                return
            }
            phase = .loaded(Image(uiImage: uiImage))
        } catch {
            phase = .failed
        }
    }
}
