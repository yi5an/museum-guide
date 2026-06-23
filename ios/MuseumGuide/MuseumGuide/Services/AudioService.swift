import AVFoundation
import Observation

@Observable
final class AudioService: NSObject {
    static let shared = AudioService()

    private let synthesizer = AVSpeechSynthesizer()
    private(set) var isPlaying = false
    private(set) var currentRange: NSRange?

    override init() {
        super.init()
        synthesizer.delegate = self
        configureAudioSession()
    }

    private func configureAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(
                .playback, mode: .spokenAudio,
                options: [.duckOthers, .interruptSpokenAudioAndMixWithOthers])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("AudioSession 配置失败: \(error)")
        }
    }

    func speak(_ text: String, lang: String) {
        stop()
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: langCodeToBcp47(lang))
        utterance.rate = 0.45
        utterance.pitchMultiplier = 1.0
        utterance.preUtteranceDelay = 0.1
        utterance.postUtteranceDelay = 0.3
        synthesizer.speak(utterance)
        isPlaying = true
    }

    func pause() {
        synthesizer.pauseSpeaking(at: .word)
        isPlaying = false
    }

    func resume() {
        synthesizer.continueSpeaking()
        isPlaying = true
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
        isPlaying = false
        currentRange = nil
    }

    func togglePlayPause() {
        if isPlaying { pause() } else { resume() }
    }

    private func langCodeToBcp47(_ lang: String) -> String {
        switch lang {
        case "zh": return "zh-CN"
        case "en": return "en-US"
        case "ja": return "ja-JP"
        case "ko": return "ko-KR"
        case "fr": return "fr-FR"
        case "es": return "es-ES"
        default: return lang
        }
    }
}

extension AudioService: AVSpeechSynthesizerDelegate {
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer,
                           willSpeakRangeOfSpeechString charRange: NSRange,
                           utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.currentRange = charRange
        }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer,
                           didFinish utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isPlaying = false
            self.currentRange = nil
        }
    }
}
