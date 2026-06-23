import SwiftUI
import SwiftData

struct ProfileView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var vm = ProfileViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    HStack(spacing: 10) {
                        statCard(num: "\(vm.museumCount)", label: "已访博物馆", color: .vermilion)
                        statCard(num: "\(vm.visitedCount)", label: "已听展品", color: .bronze)
                        statCard(num: "0h", label: "参观时长", color: .jade)
                    }.padding(.horizontal)

                    progressCard

                    if !vm.visitedExhibits.isEmpty {
                        footprintSection
                    } else {
                        VStack(spacing: 8) {
                            Image(systemName: "archivebox").font(.system(size: 40)).foregroundStyle(.inkTertiary)
                            Text("还没有参观记录，去探索博物馆吧！").foregroundStyle(.inkTertiary)
                        }.padding(.top, 40)
                    }

                    settingsList
                }.padding(.vertical)
            }
            .navigationTitle("我的")
            .background(.bgRice)
            .onAppear { vm.load(context: modelContext) }
        }
    }

    private func statCard(num: String, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(num).font(.titleLarge).foregroundStyle(color)
            Text(label).font(.caption).foregroundStyle(.inkTertiary)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 14)
        .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusMedium))
        .shadow(color: .black.opacity(0.04), radius: 2)
    }

    private var progressCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("国家博物馆 · 青铜厅").font(.caption).foregroundStyle(.white.opacity(0.9))
            HStack(alignment: .firstTextBaseline) {
                Text("\(vm.visitedCount)").font(.titleLarge)
                Text("/ 12 件展品").font(.caption).foregroundStyle(.white.opacity(0.7))
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(.white.opacity(0.2))
                    Capsule().fill(.white).frame(width: geo.size.width * 0.3)
                }
            }.frame(height: 6)
        }
        .foregroundStyle(.white).padding(16)
        .background(LinearGradient(colors: [.bronzeDeep, .bronze], startPoint: .topLeading, endPoint: .bottomTrailing),
                    in: RoundedRectangle(cornerRadius: .radiusMedium))
        .padding(.horizontal)
    }

    private var footprintSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("📍 我的足迹").font(.headline).padding(.horizontal)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(vm.visitedExhibits) { item in
                        VStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 10).fill(.bronzeDeep)
                                .frame(width: 100, height: 80)
                                .overlay(Image(systemName: "archivebox.fill").foregroundStyle(.white))
                            Text(item.exhibitName).font(.body)
                            Text(item.visitedAt.formatted(.dateTime.month().day().hour().minute()))
                                .font(.caption).foregroundStyle(.inkTertiary)
                        }.frame(width: 100)
                    }
                }.padding(.horizontal)
            }
        }
    }

    private var settingsList: some View {
        VStack(spacing: 0) {
            settingsRow(icon: "globe", label: "语言", value: "中文", color: .bronze)
            Divider()
            settingsRow(icon: "arrow.down.circle", label: "离线缓存", value: "0 MB", color: .jade)
            Divider()
            settingsRow(icon: "info.circle", label: "关于", value: nil, color: .vermilion)
        }
        .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusMedium))
        .padding(.horizontal)
    }

    private func settingsRow(icon: String, label: String, value: String?, color: Color) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .frame(width: 30, height: 30)
                .background(color.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
                .foregroundStyle(color)
            Text(label)
            Spacer()
            if let value { Text(value).foregroundStyle(.inkTertiary) }
            Image(systemName: "chevron.right").foregroundStyle(.inkTertiary.opacity(0.5))
        }.padding(14)
    }
}
