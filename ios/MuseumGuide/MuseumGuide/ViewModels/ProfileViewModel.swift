import SwiftUI
import SwiftData

@Observable
final class ProfileViewModel {
    var visitedCount: Int = 0
    var museumCount: Int = 0
    var visitedExhibits: [VisitedExhibit] = []

    func load(context: ModelContext) {
        let desc = FetchDescriptor<VisitedExhibit>(sortBy: [SortDescriptor(\.visitedAt, order: .reverse)])
        visitedExhibits = (try? context.fetch(desc)) ?? []
        visitedCount = visitedExhibits.count
        museumCount = Set(visitedExhibits.map { $0.museumId }).count
    }
}
