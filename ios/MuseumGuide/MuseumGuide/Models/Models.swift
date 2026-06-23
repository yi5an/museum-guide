import Foundation
import SwiftData

@Model
final class VisitedExhibit {
    var exhibitId: Int
    var exhibitName: String
    var museumId: Int
    var museumName: String
    var category: String?
    var dynasty: String?
    var tier: Int
    var sourceLabel: String
    var narrationText: String
    var visitedAt: Date
    var imageData: Data?

    init(exhibitId: Int, exhibitName: String, museumId: Int, museumName: String,
         category: String? = nil, dynasty: String? = nil, tier: Int = 1,
         sourceLabel: String = "官方", narrationText: String = "", imageData: Data? = nil) {
        self.exhibitId = exhibitId
        self.exhibitName = exhibitName
        self.museumId = museumId
        self.museumName = museumName
        self.category = category
        self.dynasty = dynasty
        self.tier = tier
        self.sourceLabel = sourceLabel
        self.narrationText = narrationText
        self.visitedAt = Date()
        self.imageData = imageData
    }
}

@Model
final class CachedMuseum {
    var museumId: Int
    var name: String
    var detailJSON: String

    init(museumId: Int, name: String, detailJSON: String) {
        self.museumId = museumId
        self.name = name
        self.detailJSON = detailJSON
    }
}
