import SwiftUI

struct ChatView: View {
    @Bindable var viewModel: ChatViewModel

    @FocusState private var isInputFocused: Bool
    @Namespace private var bottomAnchor

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                messageList
                inputBar
            }
            .background(Color.darkBackground)
            .navigationTitle(viewModel.activeMode.displayName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    modeSwitch
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.startNewConversation()
                    } label: {
                        Image(systemName: "plus.bubble")
                            .foregroundStyle(.white)
                    }
                }
            }
        }
    }

    // MARK: - Message List

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        MessageBubble(message: message)
                    }

                    if viewModel.isStreaming {
                        streamingIndicator
                    }

                    Color.clear
                        .frame(height: 1)
                        .id("bottom")
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: viewModel.messages.count) {
                withAnimation(.easeOut(duration: 0.3)) {
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Streaming Indicator

    private var streamingIndicator: some View {
        HStack(spacing: 6) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(viewModel.activeMode.color)
                    .frame(width: 8, height: 8)
                    .scaleEffect(viewModel.isStreaming ? 1.0 : 0.5)
                    .animation(
                        .easeInOut(duration: 0.6)
                        .repeatForever()
                        .delay(Double(index) * 0.2),
                        value: viewModel.isStreaming
                    )
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.leading, 4)
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: 12) {
            TextField("Message \(viewModel.activeMode.displayName)...", text: $viewModel.inputText, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...5)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .focused($isInputFocused)

            Button {
                let text = viewModel.inputText
                Task {
                    await viewModel.sendMessage(text: text)
                }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(
                        viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                            ? Color.gray
                            : viewModel.activeMode.color
                    )
            }
            .disabled(
                viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                || viewModel.isStreaming
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    // MARK: - Mode Switch

    private var modeSwitch: some View {
        Menu {
            ForEach(AgentMode.allCases, id: \.self) { mode in
                Button {
                    viewModel.switchMode(to: mode)
                } label: {
                    Label(mode.displayName, systemImage: mode.icon)
                }
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: viewModel.activeMode.icon)
                    .font(.caption)
                Text(viewModel.activeMode.displayName)
                    .font(.caption)
                    .fontWeight(.semibold)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(viewModel.activeMode.color.opacity(0.2))
            .foregroundStyle(viewModel.activeMode.color)
            .clipShape(Capsule())
        }
    }
}

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        if message.role == .system {
            systemMessage
        } else {
            chatBubble
        }
    }

    private var systemMessage: some View {
        Text(message.content)
            .font(.caption)
            .foregroundStyle(.secondary)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
    }

    private var chatBubble: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.isUser {
                Spacer(minLength: 60)
            }

            if !message.isUser {
                modeIndicator
            }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                Text(message.content)
                    .font(.body)
                    .foregroundStyle(message.textColor)
                    .textSelection(.enabled)

                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.secondary.opacity(0.7))
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(message.bubbleColor)
            .clipShape(
                RoundedRectangle(cornerRadius: 18)
            )

            if !message.isUser {
                Spacer(minLength: 60)
            }
        }
    }

    private var modeIndicator: some View {
        Circle()
            .fill(message.mode.color)
            .frame(width: 28, height: 28)
            .overlay {
                Image(systemName: message.mode.icon)
                    .font(.system(size: 12))
                    .foregroundStyle(.white)
            }
    }
}

// MARK: - Preview

#Preview {
    ChatView(viewModel: ChatViewModel())
        .preferredColorScheme(.dark)
}
