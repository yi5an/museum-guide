import SwiftUI

@Observable
final class NarrationViewModel {
    var narration: NarrateResponse?
    var isLoading = false
    var errorMessage: String?
    var currentExhibitId: Int = 0

    let api = APIClient.shared
    let audio = AudioService.shared

    func loadNarration(exhibitId: Int, lang: String = "zh") async {
        isLoading = true
        errorMessage = nil
        currentExhibitId = exhibitId
        do {
            let resp = try await api.narrate(exhibitId: exhibitId, lang: lang)
            self.narration = resp

            // 检查是否是失败 placeholder
            let blocks = resp.content.blocks
            if blocks.count == 1,
               let text = blocks[0].text,
               text.contains("讲解生成失败") {
                errorMessage = "AI 讲解生成失败，请稍后重试"
                self.narration = nil
            } else {
                let fullText = blocks.compactMap { $0.text }.joined(separator: "\n\n")
                if !fullText.isEmpty {
                    audio.speak(fullText, lang: lang)
                }
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func retry() {
        guard currentExhibitId > 0 else { return }
        Task { await loadNarration(exhibitId: currentExhibitId) }
    }

    func stopAudio() {
        audio.stop()
    }
}
