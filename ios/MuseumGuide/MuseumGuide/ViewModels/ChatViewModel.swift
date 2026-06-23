import SwiftUI

@Observable
final class ChatViewModel {
    struct Message: Identifiable {
        let id = UUID()
        let isUser: Bool
        let text: String
    }

    var messages: [Message] = []
    var inputText = ""
    var isLoading = false

    let api = APIClient.shared

    func send(exhibitId: Int, lang: String = "zh") async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        messages.append(Message(isUser: true, text: text))
        isLoading = true

        let history = messages.dropLast().suffix(6).map { msg in
            ChatMessage(role: msg.isUser ? "user" : "assistant", content: msg.text)
        }

        do {
            let resp = try await api.chat(exhibitId: exhibitId, lang: lang, message: text, history: Array(history))
            messages.append(Message(isUser: false, text: resp.reply))
        } catch {
            messages.append(Message(isUser: false, text: "出错了：\(error.localizedDescription)"))
        }
        isLoading = false
    }
}
