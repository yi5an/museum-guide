import SwiftUI

@Observable
final class RecognitionViewModel {
    enum State {
        case idle
        case scanning
        case confirmCandidates([CandidateDTO])
        case error(String)
    }

    var state: State = .idle
    var recognizedExhibitId: Int?
    var recognizedExhibitName: String?

    let api = APIClient.shared
    let camera = CameraManager.shared
    private let threshold = 0.85

    func captureAndRecognize(museumId: Int, heading: Double?) async {
        state = .scanning
        do {
            let photoData = try await camera.capturePhoto()
            let base64 = CameraManager.imageToBase64(photoData)
            let resp = try await api.recognize(museumId: museumId, imageBase64: base64, heading: heading)
            if resp.bestConfidence >= threshold, let best = resp.bestMatch {
                recognizedExhibitId = best.exhibitId
                recognizedExhibitName = best.name
                state = .idle
            } else {
                state = .confirmCandidates(resp.candidates)
            }
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    func confirmCandidate(_ candidate: CandidateDTO) {
        recognizedExhibitId = candidate.exhibitId
        recognizedExhibitName = candidate.name
        state = .idle
    }

    func reset() {
        state = .idle
        recognizedExhibitId = nil
        recognizedExhibitName = nil
    }
}
