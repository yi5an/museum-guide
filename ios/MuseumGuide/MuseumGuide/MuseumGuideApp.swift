import SwiftUI
import SwiftData

@main
struct MuseumGuideApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: [VisitedExhibit.self, CachedMuseum.self])
    }
}
