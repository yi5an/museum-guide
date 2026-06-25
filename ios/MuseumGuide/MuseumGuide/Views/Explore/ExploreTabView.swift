import SwiftUI

/// 博物馆建筑图片加载视图。
/// 使用独立 URLSession + .reloadIgnoringLocalCacheData，避免 AsyncImage 缓存
/// 旧的失败结果或旧版本图片，确保每次启动都拉取最新图片。
struct MuseumCoverImage: View {
    let url: String?
    var height: CGFloat = 150

    var body: some View {
        NoCacheAsyncImage(url: url.flatMap { URL(string: $0) }, height: height)
    }
}

/// 绕过 URLCache 的轻量异步图片加载器。
/// 图片用 aspectRatio(.fill) 填满后立即 clipped，确保不会撑破容器或超出裁切。
private struct NoCacheAsyncImage: View {
    let url: URL?
    var height: CGFloat
    @State private var image: Image?
    @State private var failed = false

    var body: some View {
        ZStack {
            if let image {
                image
                    .resizable()
                    .scaledToFill()
            } else {
                placeholder
            }
        }
        // 固定高度 + 裁剪，保证 fill 模式下溢出的部分被切掉
        .frame(height: height)
        .frame(maxWidth: .infinity)
        .clipped()
        .task(id: url) { if let url { await load(url) } }
    }

    @ViewBuilder
    private var placeholder: some View {
        LinearGradient(colors: [.bronzeDeep, Color.bronze],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
            .overlay {
                if failed {
                    Image(systemName: "building.columns.fill")
                        .font(.system(size: 40)).opacity(0.2).foregroundStyle(.white)
                } else {
                    ProgressView().tint(.white)
                }
            }
    }

    @MainActor
    private func load(_ url: URL) async {
        image = nil
        failed = false
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("MuseumGuide/1.0", forHTTPHeaderField: "User-Agent")
        do {
            let (data, resp) = try await URLSession.shared.data(for: request)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200,
                  let uiImage = UIImage(data: data) else {
                failed = true
                return
            }
            image = Image(uiImage: uiImage)
        } catch {
            failed = true
        }
    }
}

struct ExploreTabView: View {
    let vm: MuseumViewModel
    @State private var showCamera = false

    var body: some View {
        NavigationStack {
            ScrollView {
                if let museum = vm.currentMuseum {
                    museumContent(museum: museum)
                } else {
                    museumList
                }
            }
            .background(.bgRice)
            .navigationBarHidden(true)
            .task {
                if vm.museums.isEmpty { await vm.loadMuseumList() }
            }
            .refreshable { await vm.loadMuseumList() }
            .sheet(isPresented: $showCamera) {
                CameraView(currentMuseumId: vm.currentMuseum?.id)
            }
        }
    }

    // MARK: - 博物馆列表
    private var museumList: some View {
        VStack(spacing: 0) {
            // 顶部标题
            VStack(alignment: .leading, spacing: 6) {
                Text("探索博物馆").font(.titleLarge)
                Text("选择一家支持的博物馆，开启智能参观之旅")
                    .font(.caption).foregroundStyle(.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 24).padding(.top, 60).padding(.bottom, 20)

            LazyVStack(spacing: 14) {
                ForEach(vm.museums) { item in
                    Button { vm.selectMuseum(id: item.id) } label: {
                        museumCard(item)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 100)
        }
    }

    private func museumCard(_ item: MuseumListItemDTO) -> some View {
        ZStack(alignment: .bottomLeading) {
            // 建筑照底图（无缓存加载，确保每次拉最新图片）
            MuseumCoverImage(url: item.coverImageUrl, height: 150)

            // 渐变遮罩
            LinearGradient(
                colors: [.clear, .black.opacity(0.55)],
                startPoint: .center, endPoint: .bottom)
            .frame(height: 150)

            // 博物馆信息
            VStack(alignment: .leading, spacing: 4) {
                Text(item.name).font(.bodyEmphasis).foregroundStyle(.white)
                if let desc = item.description {
                    Text(desc).font(.caption).foregroundStyle(.white.opacity(0.85))
                        .lineLimit(1)
                }
                HStack(spacing: 8) {
                    Label(item.city, systemImage: "location.fill").font(.caption)
                    Text("·").font(.caption)
                    Text("\(item.exhibitCount) 件展品").font(.caption)
                }
                .foregroundStyle(.white.opacity(0.85))
            }
            .padding(16)
        }
        .frame(height: 150)
        .clipShape(RoundedRectangle(cornerRadius: .radiusLarge))
        .shadow(color: .black.opacity(0.08), radius: 6, y: 3)
    }

    // MARK: - 博物馆详情
    @ViewBuilder
    private func museumContent(museum: MuseumDetailDTO) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            heroHeader(museum: museum)
            VStack(alignment: .leading, spacing: 24) {
                ctaCard
                if !museum.routes.isEmpty { sectionRoute(routes: museum.routes) }
                if !museum.floors.isEmpty { sectionFloor(floors: museum.floors) }
                if !vm.exhibits.isEmpty { sectionExhibits }
            }
            .padding(.top, 24)
            .padding(.bottom, 100)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func heroHeader(museum: MuseumDetailDTO) -> some View {
        ZStack(alignment: .top) {
            // 建筑照底图（无缓存加载，自身已处理 fill+clipped）
            MuseumCoverImage(url: museum.coverImageUrl, height: 280)

            // 渐变遮罩（铺满整个区域）
            LinearGradient(
                colors: [.black.opacity(0.25), .clear, .black.opacity(0.8)],
                startPoint: .top, endPoint: .bottom)

            // 内容层：顶部按钮 + 底部信息，用 VStack + Spacer 分隔
            VStack(alignment: .leading, spacing: 0) {
                // 顶部返回/相机按钮
                HStack {
                    Button { vm.currentMuseum = nil } label: {
                        Image(systemName: "chevron.left")
                            .padding(10).background(.black.opacity(0.35), in: Circle())
                            .foregroundStyle(.white)
                    }
                    Spacer()
                    Button { showCamera = true } label: {
                        Image(systemName: "camera.fill")
                            .padding(10).background(.black.opacity(0.35), in: Circle())
                            .foregroundStyle(.white)
                    }
                }
                Spacer(minLength: 0)
                // 底部博物馆信息
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 4) {
                        Image(systemName: "location.fill")
                        Text(museum.city)
                    }
                    .font(.caption).foregroundStyle(.white)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(.white.opacity(0.18), in: Capsule())
                    Text(museum.name)
                        .font(.system(size: 28, weight: .bold))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    HStack(spacing: 12) {
                        Text("\(museum.exhibitCount) 件展品")
                        Text("·").opacity(0.5)
                        Text(museum.country)
                    }
                    .font(.caption).foregroundStyle(.white.opacity(0.9))
                    if let desc = museum.description {
                        Text(desc).font(.caption).foregroundStyle(.white.opacity(0.9))
                            .lineLimit(2)
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 56)
            .padding(.bottom, 20)
        }
        .frame(height: 280)
        .frame(maxWidth: .infinity)
        .clipped()
    }

    private var ctaCard: some View {
        Button { showCamera = true } label: {
            HStack(spacing: 14) {
                Image(systemName: "camera.viewfinder").font(.title2)
                    .frame(width: 52, height: 52)
                    .background(.white.opacity(0.2), in: RoundedRectangle(cornerRadius: 14))
                VStack(alignment: .leading, spacing: 2) {
                    Text("拍摄展品，听讲解").font(.bodyEmphasis)
                    Text("对准展品拍照，AI 自动识别讲解").font(.caption).opacity(0.85)
                }
                Spacer()
                Image(systemName: "chevron.right").opacity(0.7)
            }
            .foregroundStyle(.white).padding(20)
            .background(
                LinearGradient(colors: [.vermilion, .vermilion.opacity(0.85)],
                               startPoint: .topLeading, endPoint: .bottomTrailing),
                in: RoundedRectangle(cornerRadius: .radiusLarge))
            .shadow(color: .vermilion.opacity(0.3), radius: 12, y: 4)
        }
        .padding(.horizontal, 24)
    }

    // MARK: - 路线
    private func sectionRoute(routes: [RouteDTO]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("推荐参观路线").font(.titleSection).padding(.horizontal, 24)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(routes) { route in routeCard(route: route) }
                }.padding(.horizontal, 24)
            }
        }
    }

    private func routeCard(route: RouteDTO) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "star.fill").foregroundStyle(.vermilion)
                    .frame(width: 40, height: 40)
                    .background(.vermilionSoft, in: RoundedRectangle(cornerRadius: 12))
                Text(route.theme.uppercased()).font(.caption).foregroundStyle(.vermilion)
            }
            Text(route.title).font(.body)
            HStack(spacing: 12) {
                Label("\(route.durationMin) 分钟", systemImage: "clock")
                Text("\(route.exhibitOrder.count) 件展品")
            }
            .font(.caption).foregroundStyle(.inkTertiary)
        }
        .padding(16).frame(width: 200, alignment: .leading)
        .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusMedium))
        .shadow(color: .black.opacity(0.06), radius: 4, y: 2)
    }

    // MARK: - 楼层
    private func sectionFloor(floors: [FloorDTO]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("选择楼层").font(.titleSection).padding(.horizontal, 24)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(floors) { floor in
                        Button { vm.switchFloor(floor.id) } label: {
                            VStack(spacing: 3) {
                                Text("F\(floor.level)").font(.titleMedium)
                                Text(floor.name).font(.microTag).foregroundStyle(.inkTertiary)
                            }
                            .padding(.horizontal, 18).padding(.vertical, 12)
                            .background(
                                vm.selectedFloorId == floor.id ? AnyShapeStyle(.vermilion) : AnyShapeStyle(.bgCard),
                                in: RoundedRectangle(cornerRadius: .radiusSmall))
                            .foregroundStyle(vm.selectedFloorId == floor.id ? .white : .inkPrimary)
                        }
                    }
                }.padding(.horizontal, 24)
            }
        }
    }

    // MARK: - 展品
    private var sectionExhibits: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("本层展品 (\(vm.exhibits.count))").font(.titleSection).padding(.horizontal, 24)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(vm.exhibits) { ex in
                    NavigationLink {
                        NarrationView(exhibitId: ex.id, exhibitName: ex.name)
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            ZStack {
                                LinearGradient(colors: [.bronzeDeep, .bronze],
                                               startPoint: .topLeading, endPoint: .bottomTrailing)
                                Image(systemName: "crown.fill")
                                    .font(.system(size: 28)).opacity(0.2).foregroundStyle(.white)
                            }
                            .frame(height: 100)
                            .clipShape(RoundedRectangle(cornerRadius: .radiusSmall))
                            Text(ex.name).font(.caption).foregroundStyle(.inkPrimary)
                                .lineLimit(1)
                            if let dynasty = ex.dynasty {
                                Text(dynasty).font(.microTag).foregroundStyle(.inkTertiary)
                                    .lineLimit(1)
                            }
                        }
                        .padding(8)
                        .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusMedium))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
        }
    }
}
