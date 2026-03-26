import AVFoundation
import Foundation
import Observation
import Speech
import SwiftUI

@Observable
final class VoiceViewModel {

    // MARK: - Published State

    var voiceState: VoiceState = .idle
    var transcribedText: String = ""
    var responseText: String = ""
    var audioLevel: Float = 0.0
    var errorMessage: String?

    // MARK: - Private

    private var audioEngine = AVAudioEngine()
    private var speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var synthesizer = AVSpeechSynthesizer()
    private var audioLevelTimer: Timer?
    private var activeMode: AgentMode = .jarvis

    // MARK: - Permissions

    func requestPermissions() {
        SFSpeechRecognizer.requestAuthorization { status in
            if status != .authorized {
                Task { @MainActor in
                    self.errorMessage = "Speech recognition permission denied."
                }
            }
        }

        AVAudioApplication.requestRecordPermission { granted in
            if !granted {
                Task { @MainActor in
                    self.errorMessage = "Microphone permission denied."
                }
            }
        }
    }

    // MARK: - Start Listening

    func startListening() {
        guard voiceState == .idle || voiceState == .speaking else { return }

        // Stop any ongoing speech
        synthesizer.stopSpeaking(at: .immediate)

        // Reset
        transcribedText = ""
        errorMessage = nil

        do {
            try configureAudioSession()
            try startRecognition()
            voiceState = .listening
            startAudioLevelMonitoring()
        } catch {
            errorMessage = "Failed to start listening: \(error.localizedDescription)"
            voiceState = .idle
        }
    }

    // MARK: - Stop Listening

    func stopListening() {
        guard voiceState == .listening else { return }

        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        stopAudioLevelMonitoring()

        let finalText = transcribedText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !finalText.isEmpty else {
            voiceState = .idle
            return
        }

        voiceState = .thinking

        Task {
            await processVoiceInput(finalText)
        }
    }

    // MARK: - Toggle

    func toggleListening() {
        switch voiceState {
        case .idle:
            startListening()
        case .listening:
            stopListening()
        case .speaking:
            synthesizer.stopSpeaking(at: .immediate)
            voiceState = .idle
        case .thinking:
            break // Cannot interrupt thinking
        }
    }

    // MARK: - Set Mode

    func setMode(_ mode: AgentMode) {
        activeMode = mode
    }

    // MARK: - Private: Audio Session

    private func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
        try session.setActive(true, options: .notifyOthersOnDeactivation)
    }

    // MARK: - Private: Speech Recognition

    private func startRecognition() throws {
        recognitionTask?.cancel()
        recognitionTask = nil

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.addsPunctuation = true
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()

        recognitionTask = speechRecognizer?.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }

            if let result {
                Task { @MainActor in
                    self.transcribedText = result.bestTranscription.formattedString
                }
            }

            if error != nil || (result?.isFinal ?? false) {
                self.audioEngine.stop()
                inputNode.removeTap(onBus: 0)
                self.recognitionRequest = nil
                self.recognitionTask = nil
            }
        }
    }

    // MARK: - Private: Audio Level Monitoring

    private func startAudioLevelMonitoring() {
        audioLevelTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            guard let self, self.audioEngine.isRunning else { return }

            let level = self.audioEngine.inputNode.outputFormat(forBus: 0).channelCount > 0
                ? self.normalizedPowerLevel()
                : 0

            Task { @MainActor in
                withAnimation(.easeOut(duration: 0.1)) {
                    self.audioLevel = level
                }
            }
        }
    }

    private func stopAudioLevelMonitoring() {
        audioLevelTimer?.invalidate()
        audioLevelTimer = nil
        audioLevel = 0
    }

    private func normalizedPowerLevel() -> Float {
        // Approximate audio level from engine running state
        // In production, use AVAudioPCMBuffer power analysis
        return Float.random(in: 0.2...0.8)
    }

    // MARK: - Private: Process Voice Input

    private func processVoiceInput(_ text: String) async {
        do {
            // Simulate thinking animation
            simulateThinkingAudioLevel()

            let response = try await NexusAPI.sendChat(
                message: text,
                mode: activeMode,
                conversationId: nil
            )

            responseText = response.content
            voiceState = .speaking

            // Speak the response
            speakResponse(response.content)
        } catch {
            responseText = "Sorry, I encountered an error."
            errorMessage = error.localizedDescription
            voiceState = .idle
            stopAudioLevelMonitoring()
        }
    }

    private func simulateThinkingAudioLevel() {
        audioLevelTimer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                withAnimation(.easeInOut(duration: 0.15)) {
                    self.audioLevel = Float.random(in: 0.3...0.6)
                }
            }
        }
    }

    // MARK: - Private: Text-to-Speech

    private func speakResponse(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0

        // Monitor speaking audio level
        audioLevelTimer?.invalidate()
        audioLevelTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            guard let self else { return }
            let level: Float = self.synthesizer.isSpeaking ? Float.random(in: 0.4...0.9) : 0
            Task { @MainActor in
                withAnimation(.easeOut(duration: 0.1)) {
                    self.audioLevel = level
                }
                if !self.synthesizer.isSpeaking && self.voiceState == .speaking {
                    self.voiceState = .idle
                    self.stopAudioLevelMonitoring()
                }
            }
        }

        synthesizer.speak(utterance)
    }
}
