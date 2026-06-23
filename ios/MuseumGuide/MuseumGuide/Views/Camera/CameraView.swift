import SwiftUI
import AVFoundation

struct CameraView: View {
    let currentMuseumId: Int?
    @State private var vm = RecognitionViewModel()
    @State private var showNarration = false
    @State private var previewLayer: AVCaptureVideoPreviewLayer?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            // 全屏取景预览
            if let layer = previewLayer {
                CameraPreviewLayerView(layer: layer).ignoresSafeArea()
            } else {
                Color.black.ignoresSafeArea()
                    .overlay(
                        VStack(spacing: 8) {
                            Image(systemName: "camera.fill").font(.system(size: 40)).foregroundStyle(.white.opacity(0.3))
                            Text("模拟器无摄像头").font(.caption).foregroundStyle(.white.opacity(0.5))
                        }
                    )
            }

            VStack {
                contextBar
                Spacer()
                if case .scanning = vm.state { scanOverlay }
                Spacer()
                controls
            }
        }
        .onAppear {
            do {
                try CameraManager.shared.configureSession()
                CameraManager.shared.startSession()
                previewLayer = CameraManager.shared.makePreviewLayer()
            } catch {
                vm.state = .error(error.localizedDescription)
            }
        }
        .onDisappear { CameraManager.shared.stopSession() }
        .alert("识别出错", isPresented: .constant(isErrorState)) {
            Button("重试") { vm.reset() }
        } message: {
            if case .error(let msg) = vm.state { Text(msg) }
        }
        .sheet(isPresented: $showNarration) {
            if let exhibitId = vm.recognizedExhibitId {
                NarrationView(exhibitId: exhibitId, exhibitName: vm.recognizedExhibitName ?? "")
            }
        }
        .sheet(isPresented: .constant(isConfirmState)) {
            if case .confirmCandidates(let cands) = vm.state {
                CandidateConfirmSheet(candidates: cands) { selected in
                    vm.confirmCandidate(selected)
                    showNarration = true
                }
            }
        }
    }

    private var isErrorState: Bool {
        if case .error = vm.state { return true } else { return false }
    }
    private var isConfirmState: Bool {
        if case .confirmCandidates = vm.state { return true } else { return false }
    }

    private var contextBar: some View {
        HStack(spacing: 6) {
            Image(systemName: "location.fill")
            Text(currentMuseumId != nil ? "博物馆 #\(currentMuseumId!) · 青铜厅" : "未定位")
        }
        .font(.caption).foregroundStyle(.white)
        .padding(.horizontal, 14).padding(.vertical, 7)
        .background(.black.opacity(0.45), in: Capsule())
        .padding(.top, 60)
    }

    private var scanOverlay: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20)
                .stroke(.success.opacity(0.7), lineWidth: 2)
                .frame(width: 200, height: 200)
            ScanLineAnimation().frame(width: 200, height: 200)
        }
    }

    private var controls: some View {
        HStack {
            Image(systemName: "photo.on.rectangle")
                .frame(width: 44, height: 44)
                .background(.white.opacity(0.15), in: Circle())
                .foregroundStyle(.white)
            Spacer()
            Button {
                Task {
                    if case .scanning = vm.state {
                        vm.reset()
                    } else {
                        await vm.captureAndRecognize(museumId: currentMuseumId ?? 1, heading: nil)
                        if vm.recognizedExhibitId != nil { showNarration = true }
                    }
                }
            } label: {
                if case .scanning = vm.state {
                    Image(systemName: "xmark")
                        .frame(width: 54, height: 54)
                        .background(.white.opacity(0.2), in: Circle())
                        .foregroundStyle(.white)
                } else {
                    Circle().fill(.white).frame(width: 54, height: 54)
                        .overlay(Circle().stroke(.white.opacity(0.85), lineWidth: 3).frame(width: 68, height: 68))
                }
            }
            Spacer()
            Image(systemName: "bolt")
                .frame(width: 44, height: 44)
                .background(.white.opacity(0.15), in: Circle())
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 30).padding(.bottom, 50)
    }
}

struct CameraPreviewLayerView: UIViewRepresentable {
    let layer: AVCaptureVideoPreviewLayer
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .black
        layer.frame = view.bounds
        view.layer.addSublayer(layer)
        return view
    }
    func updateUIView(_ uiView: UIView, context: Context) {
        layer.frame = uiView.bounds
    }
}

struct ScanLineAnimation: View {
    @State private var offset: CGFloat = -90
    var body: some View {
        Rectangle()
            .fill(LinearGradient(colors: [.clear, .success, .clear],
                                 startPoint: .leading, endPoint: .trailing))
            .frame(height: 2).offset(y: offset)
            .onAppear {
                withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) {
                    offset = 90
                }
            }
    }
}

struct CandidateConfirmSheet: View {
    let candidates: [CandidateDTO]
    let onSelect: (CandidateDTO) -> Void

    var body: some View {
        VStack(spacing: 16) {
            Capsule().fill(.gray.opacity(0.3)).frame(width: 36, height: 4).padding(.top, 8)
            Text("这是哪件展品？").font(.headline)
            Text("识别到 \(candidates.count) 件相似展品，请确认")
                .font(.caption).foregroundStyle(.inkTertiary)

            ForEach(candidates) { cand in
                Button { onSelect(cand) } label: {
                    HStack {
                        RoundedRectangle(cornerRadius: 10).fill(.bronzeDeep)
                            .frame(width: 52, height: 52)
                            .overlay(Image(systemName: "archivebox.fill").foregroundStyle(.white))
                        VStack(alignment: .leading) {
                            Text(cand.name).font(.body)
                            Text("置信度 \(Int(cand.confidence * 100))%").font(.caption).foregroundStyle(.inkTertiary)
                        }
                        Spacer()
                    }
                    .padding(12)
                    .background(.bgCard, in: RoundedRectangle(cornerRadius: .radiusMedium))
                }
                .buttonStyle(.plain)
            }

            HStack {
                Button("都不是") {}.frame(maxWidth: .infinity).padding(.vertical, 14)
                    .background(.gray.opacity(0.1), in: RoundedRectangle(cornerRadius: .radiusSmall))
                Button("听讲解") { if let first = candidates.first { onSelect(first) } }
                    .frame(maxWidth: .infinity).padding(.vertical, 14)
                    .background(.ink, in: RoundedRectangle(cornerRadius: .radiusSmall))
                    .foregroundStyle(.white)
            }
        }
        .padding().presentationDetents([.medium])
    }
}
