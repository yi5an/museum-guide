import Foundation

// === 请求 DTO ===

struct LocateRequest: Codable {
    let lat: Double
    let lng: Double
}

struct RecognizeRequest: Codable {
    let museumId: Int
    let floorId: Int?
    let image: String
    let heading: Double?

    enum CodingKeys: String, CodingKey {
        case museumId = "museum_id"
        case floorId = "floor_id"
        case image, heading
    }
}

struct NarrateRequest: Codable {
    let exhibitId: Int
    let lang: String

    enum CodingKeys: String, CodingKey {
        case exhibitId = "exhibit_id"
        case lang
    }
}

struct ChatMessage: Codable {
    let role: String
    let content: String
}

struct ChatRequest: Codable {
    let exhibitId: Int
    let lang: String
    let message: String
    let chatHistory: [ChatMessage]?

    enum CodingKeys: String, CodingKey {
        case exhibitId = "exhibit_id"
        case lang, message
        case chatHistory = "chat_history"
    }
}

struct FeedbackRequest: Codable {
    let exhibitId: Int?
    let type: String
    let proposedFloorId: Int?
    let content: String?
    let heading: Double?

    enum CodingKeys: String, CodingKey {
        case exhibitId = "exhibit_id"
        case type
        case proposedFloorId = "proposed_floor_id"
        case content, heading
    }
}

// === 响应 DTO ===

struct LocateResponse: Codable {
    let museumId: Int?
    let name: String?
    let isInside: Bool

    enum CodingKeys: String, CodingKey {
        case museumId = "museum_id"
        case name
        case isInside = "is_inside"
    }
}

struct FloorDTO: Codable, Identifiable {
    let id: Int
    let level: Int
    let name: String
    let floorPlanUrl: String?
    let sortOrder: Int

    enum CodingKeys: String, CodingKey {
        case id, level, name
        case floorPlanUrl = "floor_plan_url"
        case sortOrder = "sort_order"
    }
}

struct RouteDTO: Codable, Identifiable {
    let id: Int
    let title: String
    let theme: String
    let durationMin: Int
    let exhibitOrder: [Int]

    enum CodingKeys: String, CodingKey {
        case id, title, theme
        case durationMin = "duration_min"
        case exhibitOrder = "exhibit_order"
    }
}

struct MuseumDetailDTO: Codable {
    let id: Int
    let name: String
    let nameI18n: [String: String]
    let city: String
    let country: String
    let description: String?
    let floors: [FloorDTO]
    let routes: [RouteDTO]
    let exhibitCount: Int

    enum CodingKeys: String, CodingKey {
        case id, name, city, country, description, floors, routes
        case nameI18n = "name_i18n"
        case exhibitCount = "exhibit_count"
    }
}

struct CandidateDTO: Codable, Identifiable {
    var id: String { "\(exhibitId ?? -1)_\(name)" }
    let exhibitId: Int?
    let name: String
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case exhibitId = "exhibit_id"
        case name, confidence
    }
}

struct RecognizeResponse: Codable {
    let candidates: [CandidateDTO]
    let bestMatch: CandidateDTO?
    let bestConfidence: Double

    enum CodingKeys: String, CodingKey {
        case candidates
        case bestMatch = "best_match"
        case bestConfidence = "best_confidence"
    }
}

struct NarrationBlock: Codable, Identifiable, Hashable {
    var id: String { "\(type)_\(section ?? "")_\(text ?? "")" }
    let type: String
    let section: String?
    let text: String?
    let imageId: Int?
    let caption: String?
}

struct NarrationContent: Codable {
    let blocks: [NarrationBlock]
}

struct NarrateResponse: Codable {
    let tier: Int
    let content: NarrationContent
    let sourceLabel: String
    let audioUrl: String?

    enum CodingKeys: String, CodingKey {
        case tier, content
        case sourceLabel = "source_label"
        case audioUrl = "audio_url"
    }
}

struct ChatResponse: Codable {
    let reply: String
}

struct FeedbackResponse: Codable {
    let ok: Bool
}
