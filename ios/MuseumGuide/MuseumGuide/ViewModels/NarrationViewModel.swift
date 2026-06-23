import SwiftUI

@Observable
final class NarrationViewModel {
    var narration: NarrateResponse?
    var isLoading = false
    var errorMessage: String?

    let api = APIClient.shared
    let audio = AudioService.shared

    func loadNarration(exhibitId: Int, lang: String = "zh") async {
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await api.narrate(exhibitId: exhibitId, lang: lang)
            self.narration = resp
            let fullText = resp.content.blocks.compactMap { $0.text }.joined(separator: "\n\n")
            audio.speak(fullText, lang: lang)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func stopAudio() {
        audio.stop()
    }
}
