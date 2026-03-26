import Foundation
import Speech
import AVFoundation
import Combine

/// Handles on-device speech recognition and audio playback.
@MainActor
final class SpeechService: ObservableObject {

    // MARK: - Published State

    @Published private(set) var isListening = false
    @Published private(set) var transcription = ""
    @Published private(set) var isPlaying = false
    @Published private(set) var error: String?
    @Published var continuousListening = false

    // MARK: - Private

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var audioPlayer: AVPlayer?
    private var playerObserver: Any?

    // MARK: - Authorization

    /// Request both speech recognition and microphone permissions.
    func requestAuthorization() async -> Bool {
        let speechStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }

        guard speechStatus == .authorized else {
            error = "Speech recognition not authorized."
            return false
        }

        let micStatus = await AVAudioApplication.requestRecordPermission()
        guard micStatus else {
            error = "Microphone access not authorized."
            return false
        }

        return true
    }

    // MARK: - Listening

    func startListening() throws {
        guard let speechRecognizer, speechRecognizer.isAvailable else {
            error = "Speech recognizer unavailable."
            return
        }

        // Cancel any in-flight task.
        stopListening()

        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest else { return }

        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = speechRecognizer.supportsOnDeviceRecognition

        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if let result {
                    self.transcription = result.bestTranscription.formattedString
                }
                if let error {
                    self.error = error.localizedDescription
                    self.stopListening()
                }
                if result?.isFinal == true {
                    self.stopListening()
                    if self.continuousListening {
                        try? self.startListening()
                    }
                }
            }
        }

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()

        transcription = ""
        isListening = true
        error = nil
    }

    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask?.cancel()
        recognitionTask = nil
        isListening = false
    }

    func toggleListening() throws {
        if isListening {
            stopListening()
        } else {
            try startListening()
        }
    }

    // MARK: - Audio Playback

    /// Play audio from a remote URL (e.g. TTS MP3 returned by the API).
    func playAudio(from urlString: String) {
        guard let url = URL(string: urlString) else {
            error = "Invalid audio URL."
            return
        }

        // Ensure audio session is set for playback.
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)

        let playerItem = AVPlayerItem(url: url)
        audioPlayer = AVPlayer(playerItem: playerItem)
        isPlaying = true

        // Observe when playback finishes.
        playerObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: playerItem,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.isPlaying = false
            }
        }

        audioPlayer?.play()
    }

    func stopAudio() {
        audioPlayer?.pause()
        audioPlayer = nil
        if let observer = playerObserver {
            NotificationCenter.default.removeObserver(observer)
            playerObserver = nil
        }
        isPlaying = false
    }
}
