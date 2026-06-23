import SwiftUI

struct MapTabView: View {
    @State private var vm = MapViewModel()
    @State private var museumVM = MuseumViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let museum = museumVM.currentMuseum {
                    floorSelector(floors: museum.floors)
                    ScrollView {
                        floorPlanView
                        bottomSheet
                    }
                } else if museumVM.isLoading {
                    ProgressView("加载博物馆…").padding(.top, 100)
                } else {
                    VStack {
                        Image(systemName: "map").font(.system(size: 50)).foregroundStyle(.inkTertiary)
                        Text(museumVM.errorMessage ?? "请先在探索页定位博物馆").foregroundStyle(.inkTertiary)
                    }.padding(.top, 80)
                }
            }
            .navigationTitle(museumVM.currentMuseum?.name ?? "地图")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await museumVM.loadCurrentMuseum()
                if let m = museumVM.currentMuseum { vm.bind(museum: m) }
            }
        }
    }

    private func floorSelector(floors: [FloorDTO]) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(floors) { floor in
                    Button { vm.selectedFloor = floor } label: {
                        Text("F\(floor.level) \(floor.name)")
                            .font(.caption)
                            .padding(.horizontal, 16).padding(.vertical, 7)
                            .background(vm.selectedFloor?.id == floor.id ? AnyShapeStyle(Color.ink) : AnyShapeStyle(Color.bgCard),
                                        in: Capsule())
                            .foregroundStyle(vm.selectedFloor?.id == floor.id ? .white : .inkTertiary)
                    }
                }
            }.padding()
        }
    }

    private var floorPlanView: some View {
        ZStack {
            RoundedRectangle(cornerRadius: .radiusLarge)
                .fill(Color(red: 0.93, green: 0.90, blue: 0.83))
                .padding()

            GeometryReader { geo in
                Canvas { ctx, size in
                    let w = size.width - 32
                    let h = size.height - 32
                    let rect = CGRect(x: 16, y: 16, width: w, height: h)
                    ctx.stroke(Path(rect), with: .color(.gray.opacity(0.4)), lineWidth: 1.5)

                    let cases = [
                        CGRect(x: 40, y: 50, width: 60, height: 40),
                        CGRect(x: 120, y: 50, width: 60, height: 40),
                        CGRect(x: 40, y: 140, width: 180, height: 30),
                    ]
                    for c in cases {
                        ctx.fill(Path(c), with: .color(Color.line))
                    }

                    var routePath = Path()
                    let points = [CGPoint(x: 140, y: 300), CGPoint(x: 70, y: 70),
                                  CGPoint(x: 150, y: 70), CGPoint(x: 220, y: 100)]
                    routePath.addLines(points)
                    ctx.stroke(routePath,
                               with: .color(Color(red: 0.75, green: 0.22, blue: 0.17).opacity(0.6)),
                               style: StrokeStyle(lineWidth: 2, dash: [4, 3]))

                    for (i, p) in points.enumerated() {
                        let color: Color
                        switch i {
                        case 0, 1: color = Color(red: 0.35, green: 0.49, blue: 0.43)  // jade
                        case 2: color = Color(red: 0.75, green: 0.22, blue: 0.17)     // vermilion
                        default: color = Color(red: 0.55, green: 0.41, blue: 0.08)    // bronze
                        }
                        let radius: Double = i == 2 ? 11 : 6
                        ctx.fill(Path(ellipseIn: CGRect(x: p.x - radius, y: p.y - radius,
                                                         width: radius*2, height: radius*2)),
                                 with: .color(color))
                    }
                }
            }.padding()

            VStack {
                HStack {
                    Image(systemName: "star.fill").foregroundStyle(.vermilion)
                        .frame(width: 36, height: 36)
                        .background(.vermilionSoft, in: RoundedRectangle(cornerRadius: 10))
                    VStack(alignment: .leading) {
                        Text("一小时精华路线").font(.body)
                        Text("第 3/8 站 · 下一站：四羊方尊").font(.caption).foregroundStyle(.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "xmark")
                        .frame(width: 24, height: 24).background(.line, in: Circle())
                }
                .padding(12)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: .radiusMedium))
                .padding().padding(.top, 30)
                Spacer()
            }
        }
        .frame(height: 360)
    }

    private var bottomSheet: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("路线上的展品").font(.headline)
            ForEach(0..<3) { i in
                HStack {
                    Circle().fill(i < 2 ? AnyShapeStyle(Color.jade) : AnyShapeStyle(Color.vermilion))
                        .frame(width: 24, height: 24)
                        .overlay(Text("\(i+1)").font(.caption).foregroundStyle(.white))
                    VStack(alignment: .leading) {
                        Text(["红山玉龙", "陶鹰鼎", "司母戊鼎"][i]).font(.body)
                        Text(i == 2 ? "当前位置" : "已听讲解").font(.caption).foregroundStyle(.inkTertiary)
                    }
                    Spacer()
                }.padding(.vertical, 4)
            }
        }
        .padding()
        .background(.bgCard, in: RoundedRectangle(cornerRadius: 20))
        .padding([.horizontal, .bottom])
    }
}
