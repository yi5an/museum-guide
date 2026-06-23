import SwiftUI

struct ExploreTabView: View {
    @State private var vm = MuseumViewModel()
    @State private var showCamera = false

    var body: some View {
        NavigationStack {
            ScrollView {
                if let museum = vm.currentMuseum {
                    museumContent(museum: museum)
                } else if vm.isLoading {
                    ProgressView("正在定位博物馆…").padding(.top, 100)
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "building.columns")
                            .font(.system(size: 50))
                            .foregroundStyle(.inkTertiary)
                        Text(vm.errorMessage ?? "点击下方按钮拍照识别展品")
                            .foregroundStyle(.inkTertiary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                        Button("手动选择博物馆") {
                            // 预留：手动选馆
                        }
                        .foregroundStyle(.vermilion)
                    }
                    .padding(.top, 80)
                }
            }
            .background(.bgRice)
            .navigationBarHidden(true)
            .task {
                if vm.currentMuseum == nil { await vm.loadCurrentMuseum() }
            }
            .refreshable { await vm.loadCurrentMuseum() }
            .sheet(isPresented: $showCamera) {
                CameraView(currentMuseumId: vm.currentMuseum?.id)
            }
        }
    }

    @ViewBuilder
    private func museumContent(museum: MuseumDetailDTO) -> some View {
        heroHeader(museum: museum)
        VStack(alignment: .leading, spacing: 24) {
            ctaCard
            if !museum.routes.isEmpty { sectionRoute(routes: museum.routes) }
            if !museum.floors.isEmpty { sectionFloor(floors: museum.floors) }
        }
        .padding(.top, 24)
        .padding(.bottom, 100)
    }

    private func heroHeader(museum: MuseumDetailDTO) -> some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(
                colors: [.bronzeDeep, .bronzeDeep.opacity(0.8), Color(red: 0.16, green: 0.12, blue: 0.05)],
                startPoint: .topLeading, endPoint: .bottomTrailing)
            .frame(height: 260)
            .overlay {
                Image(systemName: "grid").font(.system(size: 200)).opacity(0.05).foregroundStyle(.white)
            }
            VStack(alignment: .leading, spacing: 6) {
                HStack { Spacer(); Image(systemName: "gearshape").foregroundStyle(.white.opacity(0.8))
                    .padding(8).background(.white.opacity(0.15), in: Circle()) }
                HStack(spacing: 4) {
                    Image(systemName: "location.fill")
                    Text("已定位 · \(museum.city)")
                }
                .font(.caption).foregroundStyle(.white)
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(.white.opacity(0.15), in: Capsule())
                Text(museum.name).font(.titleLarge).foregroundStyle(.white)
                HStack(spacing: 12) {
                    Text("\(museum.exhibitCount) 件展品")
                    Text("·").opacity(0.5)
                    Text(museum.country)
                }
                .font(.caption).foregroundStyle(.white.opacity(0.85))
            }
            .padding([.horizontal, .bottom], 20).padding(.top, 60)
        }
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

    private func sectionFloor(floors: [FloorDTO]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("选择楼层").font(.titleSection).padding(.horizontal, 24)
            HStack(spacing: 10) {
                ForEach(floors) { floor in
                    VStack(spacing: 3) {
                        Text("F\(floor.level)").font(.titleMedium)
                        Text(floor.name).font(.microTag).foregroundStyle(.inkTertiary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 14)
                    .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusSmall))
                    .shadow(color: .black.opacity(0.04), radius: 2, y: 1)
                }
            }.padding(.horizontal, 24)
        }
    }
}
