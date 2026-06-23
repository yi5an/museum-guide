import AVFoundation
import Observation
import UIKit

@Observable
final class CameraManager: NSObject {
    static let shared = CameraManager()

    private let session = AVCaptureSession()
    private let output = AVCapturePhotoOutput()
    private var continuation: CheckedContinuation<Data, Error>?

    var isSessionRunning = false
    var previewLayer: AVCaptureVideoPreviewLayer?

    func configureSession() throws {
        session.beginConfiguration()
        guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            session.commitConfiguration()
            throw NSError(domain: "CameraManager", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "无后置摄像头"])
        }
        let input = try AVCaptureDeviceInput(device: camera)
        if session.canAddInput(input) { session.addInput(input) }
        if session.canAddOutput(output) { session.addOutput(output) }
        session.commitConfiguration()
    }

    func startSession() {
        guard !isSessionRunning else { return }
        DispatchQueue.global(qos: .userInitiated).async {
            self.session.startRunning()
            DispatchQueue.main.async { self.isSessionRunning = true }
        }
    }

    func stopSession() {
        guard isSessionRunning else { return }
        session.stopRunning()
        isSessionRunning = false
    }

    func capturePhoto() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            let settings = AVCapturePhotoSettings()
            settings.flashMode = .auto
            output.capturePhoto(with: settings, delegate: self)
        }
    }

    static func imageToBase64(_ data: Data, maxWidth: CGFloat = 1024) -> String {
        guard let image = UIImage(data: data) else { return "" }
        let scale = min(1.0, maxWidth / image.size.width)
        let newSize = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        UIGraphicsBeginImageContext(newSize)
        image.draw(in: CGRect(origin: .zero, size: newSize))
        let resized = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()
        return (resized?.jpegData(compressionQuality: 0.7) ?? data).base64EncodedString()
    }

    func makePreviewLayer() -> AVCaptureVideoPreviewLayer {
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        self.previewLayer = layer
        return layer
    }
}

extension CameraManager: AVCapturePhotoCaptureDelegate {
    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto,
                     error: Error?) {
        if let error = error {
            continuation?.resume(throwing: error)
        } else if let data = photo.fileDataRepresentation() {
            continuation?.resume(returning: data)
        } else {
            continuation?.resume(throwing: NSError(domain: "CameraManager", code: -2,
                userInfo: [NSLocalizedDescriptionKey: "拍照数据获取失败"]))
        }
        continuation = nil
    }
}
