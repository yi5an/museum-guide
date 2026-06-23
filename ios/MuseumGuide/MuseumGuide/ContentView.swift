import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ExploreTabView()
                .tabItem { Label("探索", systemImage: "safari") }
                .tag(0)
            MapTabView()
                .tabItem { Label("地图", systemImage: "map.fill") }
                .tag(1)
            ProfileView()
                .tabItem { Label("我的", systemImage: "person.circle") }
                .tag(2)
        }
        .tint(Color(red: 0.75, green: 0.22, blue: 0.17))
    }
}

#Preview {
    ContentView()
}
