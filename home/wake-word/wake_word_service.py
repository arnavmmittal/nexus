#!/usr/bin/env python3
"""Nexus Wake Word Detection Service.

Listens for wake words ("jarvis", "hey jarvis", "ultron") using Picovoice
Porcupine, records the following utterance, and sends it to the Nexus API
for processing. Designed to run on Raspberry Pi with minimal resources.

Usage:
    python wake_word_service.py                     # defaults from config.yaml
    python wake_word_service.py --config my.yaml    # custom config
    python wake_word_service.py --device-index 2    # specific mic
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os
import signal
import struct
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yaml

# ---------------------------------------------------------------------------
# Optional imports - graceful fallback when not on Raspberry Pi
# ---------------------------------------------------------------------------

try:
    import pvporcupine
except ImportError:
    pvporcupine = None  # type: ignore[assignment]

try:
    from pvrecorder import PvRecorder
except ImportError:
    PvRecorder = None  # type: ignore[assignment]

try:
    import RPi.GPIO as GPIO  # type: ignore[import-untyped]

    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO = None
    GPIO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus.wake_word")

# ---------------------------------------------------------------------------
# Configuration data-class
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"

BUILTIN_KEYWORDS = {"jarvis", "hey jarvis", "computer", "ok google", "alexa"}


@dataclass
class WakeWordConfig:
    """Runtime configuration loaded from config.yaml + CLI overrides."""

    nexus_api_url: str = "http://localhost:8000"
    api_key: str = ""
    picovoice_access_key: str = ""

    # Wake words ---------------------------------------------------------
    wake_words: List[str] = field(default_factory=lambda: ["jarvis"])
    sensitivities: List[float] = field(default_factory=lambda: [0.5])

    # Audio --------------------------------------------------------------
    device_index: int = -1  # -1 = system default
    sample_rate: int = 16000

    # VAD (energy-based) -------------------------------------------------
    energy_threshold: int = 500
    silence_timeout: float = 1.5  # seconds of silence to stop recording
    max_record_seconds: float = 15.0  # safety cap
    pre_speech_buffer_ms: int = 300  # keep a bit before speech starts

    # LED ----------------------------------------------------------------
    led_pin: Optional[int] = None  # GPIO pin for status LED (BCM numbering)

    # Sounds -------------------------------------------------------------
    sounds_dir: str = str(Path(__file__).parent / "sounds")
    ack_sound: str = "ack.wav"
    done_sound: str = "done.wav"
    error_sound: str = "error.wav"

    @classmethod
    def from_yaml(cls, path: Path) -> "WakeWordConfig":
        if not path.exists():
            logger.warning("Config %s not found, using defaults", path)
            return cls()

        with open(path) as fh:
            raw: Dict[str, Any] = yaml.safe_load(fh) or {}

        # Flatten nested sections
        audio = raw.get("audio", {})
        vad = raw.get("vad", {})
        led = raw.get("led", {})
        sounds = raw.get("sounds", {})
        api = raw.get("nexus", raw)

        # Build wake_words + sensitivities from list-of-dicts or plain list
        ww_raw = raw.get("wake_words", ["jarvis"])
        if ww_raw and isinstance(ww_raw[0], dict):
            words = [w["word"] for w in ww_raw]
            sens = [w.get("sensitivity", 0.5) for w in ww_raw]
        else:
            words = list(ww_raw)
            sens = [0.5] * len(words)

        return cls(
            nexus_api_url=api.get("api_url", api.get("nexus_api_url", cls.nexus_api_url)),
            api_key=api.get("api_key", os.environ.get("NEXUS_API_KEY", "")),
            picovoice_access_key=api.get(
                "picovoice_access_key",
                os.environ.get("PICOVOICE_ACCESS_KEY", ""),
            ),
            wake_words=words,
            sensitivities=sens,
            device_index=audio.get("device_index", cls.device_index),
            sample_rate=audio.get("sample_rate", cls.sample_rate),
            energy_threshold=vad.get("energy_threshold", cls.energy_threshold),
            silence_timeout=vad.get("silence_timeout", cls.silence_timeout),
            max_record_seconds=vad.get("max_record_seconds", cls.max_record_seconds),
            pre_speech_buffer_ms=vad.get("pre_speech_buffer_ms", cls.pre_speech_buffer_ms),
            led_pin=led.get("pin", cls.led_pin),
            sounds_dir=sounds.get("directory", cls.sounds_dir),
            ack_sound=sounds.get("ack", cls.ack_sound),
            done_sound=sounds.get("done", cls.done_sound),
            error_sound=sounds.get("error", cls.error_sound),
        )


# ---------------------------------------------------------------------------
# LED controller (optional GPIO)
# ---------------------------------------------------------------------------


class LEDController:
    """Simple GPIO LED with on/off/blink. No-ops when GPIO unavailable."""

    def __init__(self, pin: Optional[int] = None):
        self._pin = pin
        self._active = False
        self._blink_task: Optional[asyncio.Task[None]] = None

        if pin is not None and GPIO_AVAILABLE and GPIO is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            self._active = True
            logger.info("LED initialised on GPIO %d", pin)
        elif pin is not None:
            logger.warning("GPIO unavailable - LED disabled")

    def on(self) -> None:
        if self._active and GPIO is not None:
            self._cancel_blink()
            GPIO.output(self._pin, GPIO.HIGH)

    def off(self) -> None:
        if self._active and GPIO is not None:
            self._cancel_blink()
            GPIO.output(self._pin, GPIO.LOW)

    async def blink(self, interval: float = 0.3) -> None:
        """Start blinking in background."""
        if not self._active:
            return
        self._cancel_blink()
        self._blink_task = asyncio.create_task(self._blink_loop(interval))

    async def _blink_loop(self, interval: float) -> None:
        try:
            state = False
            while True:
                state = not state
                if GPIO is not None:
                    GPIO.output(self._pin, GPIO.HIGH if state else GPIO.LOW)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            if GPIO is not None and self._pin is not None:
                GPIO.output(self._pin, GPIO.LOW)

    def _cancel_blink(self) -> None:
        if self._blink_task and not self._blink_task.done():
            self._blink_task.cancel()
            self._blink_task = None

    def cleanup(self) -> None:
        self._cancel_blink()
        if self._active and GPIO is not None:
            GPIO.output(self._pin, GPIO.LOW)
            GPIO.cleanup(self._pin)


# ---------------------------------------------------------------------------
# Sound player
# ---------------------------------------------------------------------------


def _play_sound_sync(path: str) -> None:
    """Play a WAV file. Uses aplay on Linux, afplay on macOS."""
    if not Path(path).exists():
        logger.debug("Sound file not found: %s", path)
        return
    try:
        if sys.platform == "linux":
            os.system(f"aplay -q {path} &")
        elif sys.platform == "darwin":
            os.system(f"afplay {path} &")
    except Exception as exc:
        logger.debug("Could not play sound: %s", exc)


async def play_sound(path: str) -> None:
    """Async wrapper around sound playback."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _play_sound_sync, path)


# ---------------------------------------------------------------------------
# Wake Word Service
# ---------------------------------------------------------------------------


class WakeWordService:
    """Main service: wake word detection -> record utterance -> send to Nexus.

    Lifecycle:
        svc = WakeWordService(config)
        await svc.start()          # blocks until cancelled
        svc.shutdown()             # cleanup
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        wake_words: Optional[List[str]] = None,
        device_index: int = -1,
        sensitivity: float = 0.5,
        config: Optional[WakeWordConfig] = None,
    ):
        # Config precedence: explicit config > individual params > defaults
        if config is not None:
            self.cfg = config
        else:
            self.cfg = WakeWordConfig(
                nexus_api_url=api_url or WakeWordConfig.nexus_api_url,
                api_key=api_key or "",
                wake_words=wake_words or ["jarvis"],
                sensitivities=[sensitivity] * len(wake_words or ["jarvis"]),
                device_index=device_index,
            )

        # Override from env if not set
        if not self.cfg.api_key:
            self.cfg.api_key = os.environ.get("NEXUS_API_KEY", "")
        if not self.cfg.picovoice_access_key:
            self.cfg.picovoice_access_key = os.environ.get("PICOVOICE_ACCESS_KEY", "")

        self._porcupine: Any = None
        self._recorder: Any = None
        self._led = LEDController(self.cfg.led_pin)
        self._running = False
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Main loop: listen for wake word, record, send to Nexus."""
        self._validate_dependencies()
        self._init_porcupine()
        self._init_recorder()
        self._http = httpx.AsyncClient(timeout=30.0)
        self._running = True

        logger.info(
            "Wake word service started. Listening for: %s",
            ", ".join(self.cfg.wake_words),
        )
        logger.info("Audio device index: %d", self.cfg.device_index)
        logger.info("API endpoint: %s", self.cfg.nexus_api_url)
        self._led.off()

        try:
            while self._running:
                await self._listen_loop()
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Release all resources."""
        self._running = False

        if self._recorder is not None:
            try:
                self._recorder.stop()
                self._recorder.delete()
            except Exception:
                pass
            self._recorder = None

        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None

        self._led.cleanup()

        if self._http is not None:
            # schedule close if loop is running, else ignore
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._http.aclose())
            except RuntimeError:
                pass
            self._http = None

        logger.info("Wake word service shut down")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_dependencies() -> None:
        if pvporcupine is None:
            raise RuntimeError(
                "pvporcupine is not installed. Run: pip install pvporcupine"
            )
        if PvRecorder is None:
            raise RuntimeError(
                "pvrecorder is not installed. Run: pip install pvrecorder"
            )

    def _init_porcupine(self) -> None:
        """Create a Porcupine instance for the configured wake words."""
        access_key = self.cfg.picovoice_access_key
        if not access_key:
            raise RuntimeError(
                "Picovoice access key not set. Set PICOVOICE_ACCESS_KEY env var "
                "or picovoice_access_key in config.yaml. "
                "Get a free key at https://console.picovoice.ai/"
            )

        # Separate built-in keywords from custom .ppn paths
        builtin: List[str] = []
        custom_paths: List[str] = []
        sensitivities: List[float] = []

        for i, word in enumerate(self.cfg.wake_words):
            sens = (
                self.cfg.sensitivities[i]
                if i < len(self.cfg.sensitivities)
                else 0.5
            )
            if word.lower().replace(" ", "") in {
                k.replace(" ", "") for k in BUILTIN_KEYWORDS
            }:
                builtin.append(word.lower().replace(" ", ""))
                sensitivities.append(sens)
            elif Path(word).suffix == ".ppn":
                custom_paths.append(word)
                sensitivities.append(sens)
            else:
                # Treat as built-in (porcupine will raise if invalid)
                builtin.append(word.lower())
                sensitivities.append(sens)

        kwargs: Dict[str, Any] = {
            "access_key": access_key,
            "sensitivities": sensitivities,
        }
        if builtin:
            kwargs["keywords"] = builtin
        if custom_paths:
            kwargs["keyword_paths"] = custom_paths

        self._porcupine = pvporcupine.create(**kwargs)
        logger.info(
            "Porcupine initialised (sample_rate=%d, frame_length=%d)",
            self._porcupine.sample_rate,
            self._porcupine.frame_length,
        )

    def _init_recorder(self) -> None:
        """Create a PvRecorder matched to Porcupine's frame size."""
        device_idx = self.cfg.device_index if self.cfg.device_index >= 0 else -1
        self._recorder = PvRecorder(
            frame_length=self._porcupine.frame_length,
            device_index=device_idx,
        )
        self._recorder.start()
        logger.info("Microphone recorder started")

    # ------------------------------------------------------------------
    # Main listening loop
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        """Read one frame from mic and check for wake word (non-blocking)."""
        loop = asyncio.get_running_loop()

        # Read one frame from the recorder (blocking call, run in executor)
        pcm = await loop.run_in_executor(None, self._recorder.read)

        keyword_index = self._porcupine.process(pcm)

        if keyword_index >= 0:
            wake_word = (
                self.cfg.wake_words[keyword_index]
                if keyword_index < len(self.cfg.wake_words)
                else "unknown"
            )
            await self._on_wake_word(keyword_index, wake_word)

    async def _on_wake_word(self, keyword_index: int, wake_word: str) -> None:
        """Handle a detected wake word: ack -> record -> send."""
        logger.info("Wake word detected: '%s' (index=%d)", wake_word, keyword_index)
        self._led.on()

        # Play acknowledgment sound
        ack_path = os.path.join(self.cfg.sounds_dir, self.cfg.ack_sound)
        await play_sound(ack_path)

        try:
            # Record the user's utterance
            await self._led.blink(0.2)
            audio_bytes = await self._record_utterance()

            if len(audio_bytes) < 1600:
                # Too short - probably just noise
                logger.info("Recording too short (%d bytes), ignoring", len(audio_bytes))
                self._led.off()
                return

            logger.info("Recorded %d bytes of audio", len(audio_bytes))

            # Send to Nexus
            self._led.on()
            success = await self._send_to_nexus(audio_bytes, wake_word)

            # Play completion or error sound
            if success:
                done_path = os.path.join(self.cfg.sounds_dir, self.cfg.done_sound)
                await play_sound(done_path)
            else:
                err_path = os.path.join(self.cfg.sounds_dir, self.cfg.error_sound)
                await play_sound(err_path)

        except Exception as exc:
            logger.error("Error processing wake word: %s", exc, exc_info=True)
            err_path = os.path.join(self.cfg.sounds_dir, self.cfg.error_sound)
            await play_sound(err_path)
        finally:
            self._led.off()

    # ------------------------------------------------------------------
    # Recording with energy-based VAD
    # ------------------------------------------------------------------

    async def _record_utterance(self) -> bytes:
        """Record audio until silence is detected.

        Uses simple energy-based voice activity detection:
        - Frame energy above threshold = speech
        - energy_threshold consecutive low-energy frames spanning
          silence_timeout seconds = end of speech.

        Returns raw PCM 16-bit mono audio at the configured sample rate.
        """
        loop = asyncio.get_running_loop()
        frame_length = self._porcupine.frame_length
        sample_rate = self._porcupine.sample_rate

        frames_per_second = sample_rate / frame_length
        max_frames = int(self.cfg.max_record_seconds * frames_per_second)
        silence_frames_needed = int(self.cfg.silence_timeout * frames_per_second)

        all_frames: List[bytes] = []
        silence_frame_count = 0
        speech_detected = False
        frame_count = 0

        logger.debug("Recording... (threshold=%d, silence_timeout=%.1fs)",
                      self.cfg.energy_threshold, self.cfg.silence_timeout)

        while frame_count < max_frames:
            pcm = await loop.run_in_executor(None, self._recorder.read)
            frame_count += 1

            # Convert to bytes
            pcm_bytes = struct.pack(f"{len(pcm)}h", *pcm)
            all_frames.append(pcm_bytes)

            # Calculate RMS energy of the frame
            energy = self._frame_energy(pcm)

            if energy > self.cfg.energy_threshold:
                speech_detected = True
                silence_frame_count = 0
            else:
                silence_frame_count += 1

            # Stop after silence_timeout of silence AFTER speech was detected
            if speech_detected and silence_frame_count >= silence_frames_needed:
                logger.debug("Silence detected after %d frames", frame_count)
                break

            # Also stop if we haven't heard any speech after 5 seconds
            if not speech_detected and frame_count > int(5 * frames_per_second):
                logger.debug("No speech detected after 5s, stopping")
                break

        return b"".join(all_frames)

    @staticmethod
    def _frame_energy(pcm: List[int]) -> float:
        """Calculate RMS energy of a PCM frame."""
        if not pcm:
            return 0.0
        sum_sq = sum(s * s for s in pcm)
        return (sum_sq / len(pcm)) ** 0.5

    # ------------------------------------------------------------------
    # Nexus API communication
    # ------------------------------------------------------------------

    async def _send_to_nexus(self, audio: bytes, wake_word: str) -> bool:
        """Send recorded audio to the Nexus API.

        Posts to /api/v1/shortcut/voice as a WAV file attachment.
        Falls back to /api/v1/voice/transcribe + /api/v1/shortcut/voice
        if the direct upload fails.

        Returns True on success.
        """
        if self._http is None:
            logger.error("HTTP client not initialised")
            return False

        headers: Dict[str, str] = {}
        if self.cfg.api_key:
            headers["X-API-Key"] = self.cfg.api_key

        # Package PCM as WAV
        wav_bytes = self._pcm_to_wav(audio)

        # Strategy 1: Send audio to transcribe endpoint, then text to voice
        try:
            return await self._transcribe_and_send(wav_bytes, wake_word, headers)
        except Exception as exc:
            logger.warning("Transcribe-and-send failed: %s. Trying direct upload.", exc)

        # Strategy 2: Try posting audio directly to shortcut/voice
        try:
            return await self._send_audio_direct(wav_bytes, wake_word, headers)
        except Exception as exc:
            logger.error("Direct audio send also failed: %s", exc)
            return False

    async def _transcribe_and_send(
        self, wav_bytes: bytes, wake_word: str, headers: Dict[str, str]
    ) -> bool:
        """Transcribe audio via Whisper, then send text to shortcut/voice."""
        assert self._http is not None

        # Step 1: Transcribe
        transcribe_url = f"{self.cfg.nexus_api_url}/api/v1/voice/transcribe"
        files = {"audio": ("recording.wav", wav_bytes, "audio/wav")}

        resp = await self._http.post(transcribe_url, files=files, headers=headers)
        resp.raise_for_status()
        transcript = resp.json().get("text", "").strip()

        if not transcript:
            logger.warning("Transcription returned empty text")
            return False

        logger.info("Transcribed: '%s'", transcript)

        # Step 2: Send text to shortcut voice endpoint
        voice_url = f"{self.cfg.nexus_api_url}/api/v1/shortcut/voice"
        payload = {
            "text": transcript,
            "voice_response": False,  # audio handled locally
            "context": "brief",
        }
        resp = await self._http.post(voice_url, json=payload, headers=headers)
        resp.raise_for_status()

        result = resp.json()
        response_text = result.get("speech", result.get("text", ""))
        logger.info("Nexus response: '%s'", response_text[:120])
        return True

    async def _send_audio_direct(
        self, wav_bytes: bytes, wake_word: str, headers: Dict[str, str]
    ) -> bool:
        """Upload WAV directly to Nexus (fallback)."""
        assert self._http is not None

        url = f"{self.cfg.nexus_api_url}/api/v1/voice/transcribe"
        files = {"audio": ("recording.wav", wav_bytes, "audio/wav")}
        resp = await self._http.post(url, files=files, headers=headers)
        resp.raise_for_status()

        transcript = resp.json().get("text", "")
        if transcript:
            logger.info("Fallback transcription: '%s'", transcript)
            # At minimum, log it; could also forward to another endpoint
            return True
        return False

    def _pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """Wrap raw PCM data in a WAV container."""
        sample_rate = (
            self._porcupine.sample_rate if self._porcupine else self.cfg.sample_rate
        )
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Sound helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _play_sound(sound_file: str) -> None:
        """Play a WAV file for acknowledgment/completion."""
        await play_sound(sound_file)

    # ------------------------------------------------------------------
    # Device listing utility
    # ------------------------------------------------------------------

    @staticmethod
    def list_audio_devices() -> List[str]:
        """List available audio input devices."""
        if PvRecorder is None:
            return ["pvrecorder not installed"]
        return PvRecorder.get_available_devices()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nexus Wake Word Detection Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        default=None,
        help="Audio device index (-1 for system default)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    parser.add_argument(
        "--access-key",
        type=str,
        default=None,
        help="Picovoice access key (overrides config/env)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


async def _run(cfg: WakeWordConfig) -> None:
    service = WakeWordService(config=cfg)

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal")
        service._running = False
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await service.start()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger("nexus.wake_word").setLevel(logging.DEBUG)

    # List devices and exit
    if args.list_devices:
        print("Available audio input devices:")
        for i, name in enumerate(WakeWordService.list_audio_devices()):
            print(f"  [{i}] {name}")
        sys.exit(0)

    # Load config
    cfg = WakeWordConfig.from_yaml(args.config)

    # CLI overrides
    if args.device_index is not None:
        cfg.device_index = args.device_index
    if args.access_key:
        cfg.picovoice_access_key = args.access_key

    # Validate early
    if not cfg.picovoice_access_key:
        print(
            "ERROR: Picovoice access key required.\n"
            "  Set PICOVOICE_ACCESS_KEY environment variable, or\n"
            "  pass --access-key, or set picovoice_access_key in config.yaml.\n"
            "  Get a free key at https://console.picovoice.ai/",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting Nexus Wake Word Service...")
    print(f"  Wake words : {', '.join(cfg.wake_words)}")
    print(f"  API        : {cfg.nexus_api_url}")
    print(f"  Device     : {'default' if cfg.device_index < 0 else cfg.device_index}")
    print()

    try:
        asyncio.run(_run(cfg))
    except KeyboardInterrupt:
        print("\nShutdown complete.")


if __name__ == "__main__":
    main()
