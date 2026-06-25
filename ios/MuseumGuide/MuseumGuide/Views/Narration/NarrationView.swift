import SwiftUI
import SwiftData

struct NarrationView: View {
    let exhibitId: Int
    let exhibitName: String
    @State private var vm = NarrationViewModel()
    @State private var showChat = false
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header

                    if vm.isLoading {
                        VStack(spacing: 12) {
                            ProgressView()
                                .scaleEffect(1.2)
                            Text("AI 正在生成讲解…").font(.body).foregroundStyle(Color.inkSecondary)
                            Text("这可能需要几秒钟").font(.caption).foregroundStyle(.inkTertiary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 40)
                    } else if let narration = vm.narration {
                        playerControl(tier: narration.tier, sourceLabel: narration.sourceLabel)
                        narrationContent(blocks: narration.content.blocks)
                    } else if let error = vm.errorMessage {
                        // 错误状态 + 重试
                        VStack(spacing: 16) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.system(size: 40)).foregroundStyle(.inkTertiary)
                            Text(error).font(.body).foregroundStyle(Color.inkSecondary)
                                .multilineTextAlignment(.center)
                            Button {
                                vm.retry()
                            } label: {
                                Label("重试", systemImage: "arrow.clockwise")
                                    .padding(.horizontal, 24).padding(.vertical, 10)
                                    .background(Color.vermilion, in: Capsule())
                                    .foregroundStyle(.white)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 40)
                    }
                }
                .padding()
            }
            .background(.bgRice)
            .navigationTitle(exhibitName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { dismiss() } label: { Image(systemName: "xmark.circle.fill") }
                        .tint(.inkTertiary)
                }
            }
            .task {
                await vm.loadNarration(exhibitId: exhibitId)
                // 讲解成功后保存足迹
                if let narration = vm.narration {
                    let visited = VisitedExhibit(
                        exhibitId: exhibitId,
                        exhibitName: exhibitName,
                        museumId: 0,
                        museumName: "国家博物馆",
                        tier: narration.tier,
                        sourceLabel: narration.sourceLabel,
                        narrationText: narration.content.blocks.compactMap { $0.text }.joined(separator: "\n")
                    )
                    modelContext.insert(visited)
                    try? modelContext.save()
                }
            }
            .onDisappear { vm.stopAudio() }
            .sheet(isPresented: $showChat) {
                ChatView(exhibitId: exhibitId, exhibitName: exhibitName)
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(exhibitName).font(.titleMedium)
            if let narration = vm.narration {
                Text(narration.sourceLabel).font(.microTag)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(narration.tier == 1 ? AnyShapeStyle(Color.jadeSoft) : AnyShapeStyle(Color.orange.opacity(0.2)),
                                in: RoundedRectangle(cornerRadius: 6))
                    .foregroundStyle(narration.tier == 1 ? .jade : .orange)
            }
        }
    }

    private func playerControl(tier: Int, sourceLabel: String) -> some View {
        HStack(spacing: 12) {
            Button { AudioService.shared.togglePlayPause() } label: {
                Image(systemName: AudioService.shared.isPlaying ? "pause.fill" : "play.fill")
                    .font(.title2).frame(width: 44, height: 44)
                    .background(.vermilion, in: Circle()).foregroundStyle(.white)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(AudioService.shared.isPlaying ? "正在朗读" : "已暂停 · 点击继续")
                    .font(.caption).foregroundStyle(.white.opacity(0.7))
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(.white.opacity(0.2))
                        Capsule().fill(.vermilion).frame(width: geo.size.width * 0.35)
                    }
                }.frame(height: 3)
            }
        }
        .padding(14)
        .background(.ink, in: RoundedRectangle(cornerRadius: .radiusMedium))
    }

    private func narrationContent(blocks: [NarrationBlock]) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            ForEach(blocks) { block in
                if block.type == "text", let section = block.section, let text = block.text {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Rectangle().fill(.vermilion).frame(width: 3, height: 12)
                            Text(section).font(.sectionHeading).foregroundStyle(.bronze)
                        }
                        Text(text).font(.narrationBody).foregroundStyle(.inkSecondary).lineSpacing(4)
                    }
                } else if block.type == "image" {
                    RoundedRectangle(cornerRadius: .radiusSmall).fill(.bronzeDeep.opacity(0.3)).frame(height: 100)
                        .overlay {
                            VStack {
                                Image(systemName: "photo")
                                if let cap = block.caption { Text(cap).font(.caption) }
                            }.foregroundStyle(.inkTertiary)
                        }
                }
            }
        }
    }
}
