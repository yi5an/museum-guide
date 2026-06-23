import Foundation
import Observation

enum APIError: Error, LocalizedError {
    case invalidURL
    case requestFailed(Int, String)
    case decodingFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "无效的请求地址"
        case .requestFailed(let code, let msg): return "请求失败 (\(code)): \(msg)"
        case .decodingFailed: return "数据解析失败"
        }
    }
}

@Observable
final class APIClient {
    static let shared = APIClient()

    #if DEBUG
    private let baseURL = URL(string: "http://localhost:8000")!
    #else
    private let baseURL = URL(string: "https://api.museumguide.app")!
    #endif

    private let session: URLSession
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)
    }

    func locate(lat: Double, lng: Double) async throws -> LocateResponse {
        try await post("/api/museums/locate", body: LocateRequest(lat: lat, lng: lng))
    }

    func museumDetail(id: Int) async throws -> MuseumDetailDTO {
        try await get("/api/museums/\(id)")
    }

    func recognize(museumId: Int, imageBase64: String, heading: Double?) async throws -> RecognizeResponse {
        try await post("/api/recognize", body: RecognizeRequest(
            museumId: museumId, floorId: nil, image: imageBase64, heading: heading))
    }

    func narrate(exhibitId: Int, lang: String) async throws -> NarrateResponse {
        try await post("/api/narrate", body: NarrateRequest(exhibitId: exhibitId, lang: lang))
    }

    func chat(exhibitId: Int, lang: String, message: String, history: [ChatMessage]) async throws -> ChatResponse {
        try await post("/api/chat", body: ChatRequest(
            exhibitId: exhibitId, lang: lang, message: message, chatHistory: history))
    }

    func feedback(exhibitId: Int?, type: String, content: String?, heading: Double?) async throws -> FeedbackResponse {
        try await post("/api/feedback", body: FeedbackRequest(
            exhibitId: exhibitId, type: type, proposedFloorId: nil, content: content, heading: heading))
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let url = baseURL.appendingPathComponent(path)
        let (data, response) = try await session.data(from: url)
        try checkResponse(response, data)
        return try decode(data)
    }

    private func post<B: Encodable, T: Decodable>(_ path: String, body: B) async throws -> T {
        let url = baseURL.appendingPathComponent(path)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data)
        return try decode(data)
    }

    private func checkResponse(_ response: URLResponse, _ data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.requestFailed(0, "非 HTTP 响应")
        }
        guard (200...299).contains(http.statusCode) else {
            let msg = String(data: data, encoding: .utf8) ?? "未知错误"
            throw APIError.requestFailed(http.statusCode, msg)
        }
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            print("解码失败: \(error)\n原始: \(String(data: data, encoding: .utf8) ?? "?")")
            throw APIError.decodingFailed
        }
    }
}
