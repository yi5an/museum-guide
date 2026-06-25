import SwiftUI

struct MapTabView: View {
    let vm: MuseumViewModel
    @State private var selectedExhibit: ExhibitListItem?

    var body: some View {
        NavigationStack {
            if let museum = vm.currentMuseum {
                VStack(spacing: 0) {
                    if !museum.floors.isEmpty {
                        floorSelector(floors: museum.floors)
                    }
                    mapCanvas
                    exhibitList
                }
                .navigationTitle(museum.name)
                .navigationBarTitleDisplayMode(.inline)
            } else {
                // 未选择博物馆：提示去探索页选
                VStack(spacing: 16) {
                    Image(systemName: "map")
                        .font(.system(size: 50))
                        .foregroundStyle(.inkTertiary)
                    Text("请先在「探索」中选择一家博物馆")
                        .font(.body)
                        .foregroundStyle(.inkTertiary)
                        .multilineTextAlignment(.center)
                    Text("地图会展示所选博物馆各楼层的展品分布")
                        .font(.caption)
                        .foregroundStyle(.inkTertiary)
                }
                .padding(.horizontal, 40)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .navigationTitle("地图")
                .navigationBarTitleDisplayMode(.inline)
            }
        }
        .sheet(item: $selectedExhibit) { item in
            NarrationView(exhibitId: item.id, exhibitName: item.name)
        }
    }

    private func floorSelector(floors: [FloorDTO]) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(floors) { floor in
                    let isSelected = vm.selectedFloorId == floor.id
                    Button { vm.switchFloor(floor.id) } label: {
                        Text(floor.level < 0 ? "B\(abs(floor.level)) \(floor.name)" : "F\(floor.level) \(floor.name)")
                            .font(.caption)
                            .padding(.horizontal, 16).padding(.vertical, 7)
                            .background(isSelected ? AnyShapeStyle(Color.ink) : AnyShapeStyle(Color.bgCard), in: Capsule())
                            .foregroundStyle(isSelected ? .white : .inkTertiary)
                    }
                }
            }.padding(.horizontal).padding(.vertical, 8)
        }
    }

    private var mapCanvas: some View {
        GeometryReader { geo in
            let exhibits = vm.exhibits
            // 收集有真实坐标的展品；没有坐标的展品用网格自动分布
            let positioned: [(item: ExhibitListItem, x: CGFloat, y: CGFloat)] = {
                let real = exhibits.filter { $0.planX != nil && $0.planY != nil }
                let padX: CGFloat = 32, padY: CGFloat = 32
                if !real.isEmpty {
                    let xs = real.compactMap { $0.planX! }
                    let ys = real.compactMap { $0.planY! }
                    let minX = xs.min()!, maxX = xs.max()!
                    let minY = ys.min()!, maxY = ys.max()!
                    return exhibits.enumerated().map { idx, item in
                        if let px = item.planX, let py = item.planY {
                            let nx = CGFloat((px - minX) / max(maxX - minX, 1))
                            let ny = CGFloat((py - minY) / max(maxY - minY, 1))
                            let sx = padX + nx * (geo.size.width - padX * 2)
                            let sy = padY + ny * (geo.size.height - padY * 2)
                            return (item, sx, sy)
                        } else {
                            // 没坐标的，随机但稳定地散开
                            return gridPos(item: item, idx: idx, total: exhibits.count,
                                           w: geo.size.width, h: geo.size.height, padX: padX, padY: padY)
                        }
                    }
                } else {
                    // 全都没坐标 → 网格均匀分布
                    return exhibits.enumerated().map { idx, item in
                        gridPos(item: item, idx: idx, total: exhibits.count,
                                w: geo.size.width, h: geo.size.height, padX: padX, padY: padY)
                    }
                }
            }()

            ZStack {
                RoundedRectangle(cornerRadius: .radiusLarge)
                    .fill(Color.bronzeSoft)

                Canvas { ctx, size in
                    let inset: CGFloat = 16
                    let rect = CGRect(x: inset, y: inset,
                                      width: max(size.width - inset * 2, 0),
                                      height: max(size.height - inset * 2, 0))
                    ctx.stroke(Path(rect), with: .color(.gray.opacity(0.3)), lineWidth: 1.5)
                }

                if positioned.isEmpty {
                    Text("该楼层暂无展品")
                        .font(.caption).foregroundStyle(.inkTertiary)
                } else {
                    ForEach(positioned, id: \.item.id) { p in
                        Button {
                            selectedExhibit = p.item
                        } label: {
                            Circle()
                                .fill(p.item.hasNarration ? Color.vermilion : Color.bronze)
                                .frame(width: 14, height: 14)
                                .overlay(Circle().stroke(.white, lineWidth: 1.5))
                                .shadow(color: .black.opacity(0.2), radius: 2)
                        }
                        .position(x: p.x, y: p.y)
                    }
                }

                // 图例（贴底）
                VStack {
                    Spacer()
                    HStack(spacing: 16) {
                        Label("有讲解", systemImage: "circle.fill").foregroundStyle(.vermilion)
                        Label("待生成", systemImage: "circle.fill").foregroundStyle(.bronze)
                        Spacer()
                        Text("\(exhibits.count) 件").font(.caption).foregroundStyle(.inkTertiary)
                    }
                    .font(.caption)
                    .padding(10)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
                    .padding()
                }
            }
        }
        .frame(height: 300)
        .padding(.horizontal)
    }

    /// 没有真实坐标时，按网格把展品均匀分布到画布上
    private func gridPos(item: ExhibitListItem, idx: Int, total: Int,
                         w: CGFloat, h: CGFloat, padX: CGFloat, padY: CGFloat)
        -> (item: ExhibitListItem, x: CGFloat, y: CGFloat) {
        let cols = max(Int(ceil(sqrt(Double(total)))), 2)
        let rows = max(Int(ceil(Double(total) / Double(cols))), 1)
        let col = idx % cols
        let row = idx / cols
        let stepX = (w - padX * 2) / CGFloat(max(cols - 1, 1))
        let stepY = (h - padY * 2) / CGFloat(max(rows - 1, 1))
        let x = padX + CGFloat(col) * stepX
        let y = padY + CGFloat(row) * stepY
        return (item, x, y)
    }

    private var exhibitList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("本层展品 · 点击听讲解").font(.headline).padding(.horizontal)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(vm.exhibits.prefix(30)) { item in
                        Button { selectedExhibit = item } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Circle()
                                    .fill(item.hasNarration ? Color.vermilion : Color.bronze)
                                    .frame(width: 36, height: 36)
                                    .overlay(
                                        Image(systemName: item.hasNarration ? "speaker.wave.2.fill" : "sparkles")
                                            .font(.caption).foregroundStyle(.white)
                                    )
                                Text(item.name).font(.caption).foregroundStyle(Color.ink).lineLimit(1)
                                Text(item.dynasty ?? "").font(.microTag).foregroundStyle(.inkTertiary).lineLimit(1)
                            }
                            .frame(width: 80)
                            .padding(8)
                            .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusSmall))
                            .shadow(color: .black.opacity(0.04), radius: 2)
                        }
                        .buttonStyle(.plain)
                    }
                }.padding(.horizontal)
            }
        }
        .padding(.bottom)
    }
}
