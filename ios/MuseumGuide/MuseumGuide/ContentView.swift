import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            Text("探索")
                .tabItem { Label("探索", systemImage: "safari") }
                .tag(0)
            Text("地图")
                .tabItem { Label("地图", systemImage: "map.fill") }
                .tag(1)
            Text("我的")
                .tabItem { Label("我的", systemImage: "person.circle") }
                .tag(2)
        }
        .tint(.vermilion)
    }
}

#Preview {
    ContentView()
}
