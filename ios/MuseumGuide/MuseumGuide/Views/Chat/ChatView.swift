import SwiftUI

struct ChatView: View {
    let exhibitId: Int
    let exhibitName: String
    @State private var vm = ChatViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView {
                    LazyVStack(spacing: 14) {
                        if vm.messages.isEmpty {
                            Text("关于\(exhibitName)，你想了解什么？")
                                .foregroundStyle(.inkTertiary).padding(.top, 60)
                        }
                        ForEach(vm.messages) { msg in messageBubble(msg) }
                        if vm.isLoading {
                            HStack { ProgressView(); Text("思考中…") }.foregroundStyle(.inkTertiary)
                        }
                    }.padding()
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(["铭文含义", "出土故事", "铸造工艺", "为什么这么大"], id: \.self) { q in
                            Button(q) { vm.inputText = q }
                                .font(.caption)
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .background(.bronzeSoft, in: Capsule())
                                .foregroundStyle(.bronzeDeep)
                        }
                    }.padding(.horizontal)
                }

                HStack {
                    TextField("追问任何问题…", text: $vm.inputText, axis: .vertical)
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .background(.bgRice, in: RoundedRectangle(cornerRadius: 20))
                    Button {
                        Task { await vm.send(exhibitId: exhibitId) }
                    } label: {
                        Image(systemName: "paperplane.fill")
                            .frame(width: 38, height: 38)
                            .background(.vermilion, in: Circle()).foregroundStyle(.white)
                    }
                }.padding()
            }
            .navigationTitle(exhibitName)
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func messageBubble(_ msg: ChatViewModel.Message) -> some View {
        HStack {
            if msg.isUser { Spacer() }
            Text(msg.text)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(msg.isUser ? AnyShapeStyle(Color.ink) : AnyShapeStyle(Color.bgCard),
                            in: RoundedRectangle(cornerRadius: 16))
                .foregroundStyle(msg.isUser ? .white : .inkSecondary)
                .frame(maxWidth: 280, alignment: msg.isUser ? .trailing : .leading)
            if !msg.isUser { Spacer() }
        }
    }
}
