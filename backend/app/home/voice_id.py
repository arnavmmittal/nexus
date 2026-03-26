"""Voice identification service — lightweight speaker recognition using MFCCs.

Extracts mel-frequency cepstral coefficients from audio, averages them into a
voice "fingerprint", and matches against enrolled profiles via cosine similarity.
No heavy ML dependencies — just numpy + scipy.
"""
from __future__ import annotations

import json
import logging
import math
import struct
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_MFCC = 13
NUM_MEL_FILTERS = 26
FFT_SIZE = 512
HOP_LENGTH = 256
PRE_EMPHASIS = 0.97
MIN_SAMPLES_FOR_ID = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass
class VoiceProfile:
    """Stored voice profile for a family member."""

    member_id: str
    embeddings: list[list[float]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sample_count: int = 0


# ---------------------------------------------------------------------------
# MFCC feature extraction (pure numpy + light scipy)
# ---------------------------------------------------------------------------

def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _mel_filter_bank(num_filters: int, fft_size: int, sample_rate: int) -> np.ndarray:
    """Build a mel-spaced triangular filter bank."""
    low_mel = _hz_to_mel(0)
    high_mel = _hz_to_mel(sample_rate / 2)
    mel_points = np.linspace(low_mel, high_mel, num_filters + 2)
    hz_points = np.array([_mel_to_hz(m) for m in mel_points])
    bin_points = np.floor((fft_size + 1) * hz_points / sample_rate).astype(int)

    filters = np.zeros((num_filters, fft_size // 2 + 1))
    for i in range(num_filters):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        for j in range(left, center):
            if center != left:
                filters[i, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                filters[i, j] = (right - j) / (right - center)
    return filters


def _extract_mfcc(signal: np.ndarray, sample_rate: int) -> np.ndarray:
    """Extract MFCCs from a 1-D float audio signal.

    Returns shape (num_frames, NUM_MFCC).
    """
    # Pre-emphasis
    emphasized = np.append(signal[0], signal[1:] - PRE_EMPHASIS * signal[:-1])

    # Framing
    frame_length = FFT_SIZE
    num_frames = max(1, 1 + (len(emphasized) - frame_length) // HOP_LENGTH)
    frames = np.zeros((num_frames, frame_length))
    for i in range(num_frames):
        start = i * HOP_LENGTH
        end = start + frame_length
        chunk = emphasized[start:end]
        frames[i, : len(chunk)] = chunk

    # Windowing (Hamming)
    frames *= np.hamming(frame_length)

    # FFT -> power spectrum
    mag = np.abs(np.fft.rfft(frames, n=FFT_SIZE))
    power = (1.0 / FFT_SIZE) * (mag ** 2)

    # Mel filter bank
    fb = _mel_filter_bank(NUM_MEL_FILTERS, FFT_SIZE, sample_rate)
    mel_spec = np.dot(power, fb.T)
    mel_spec = np.where(mel_spec == 0, np.finfo(float).eps, mel_spec)
    log_mel = np.log(mel_spec)

    # DCT (type-II, orthogonal) — keep first NUM_MFCC coefficients
    # Manual DCT to avoid scipy.fft dependency
    num_filters = log_mel.shape[1]
    n = np.arange(num_filters)
    dct_matrix = np.zeros((NUM_MFCC, num_filters))
    for k in range(NUM_MFCC):
        dct_matrix[k] = np.cos(np.pi * k * (2 * n + 1) / (2 * num_filters))
    mfcc = np.dot(log_mel, dct_matrix.T)

    return mfcc  # (num_frames, NUM_MFCC)


# ---------------------------------------------------------------------------
# Audio decoding helpers
# ---------------------------------------------------------------------------

def _bytes_to_signal(audio_data: bytes, sample_rate: int) -> np.ndarray:
    """Convert raw audio bytes to a numpy float32 array.

    Supports:
    - WAV files (auto-detected by RIFF header)
    - Raw 16-bit signed little-endian PCM
    """
    if audio_data[:4] == b"RIFF":
        return _decode_wav(audio_data)

    # Assume raw 16-bit signed LE PCM
    num_samples = len(audio_data) // 2
    samples = struct.unpack(f"<{num_samples}h", audio_data[: num_samples * 2])
    return np.array(samples, dtype=np.float32) / 32768.0


def _decode_wav(data: bytes) -> np.ndarray:
    """Minimal WAV decoder — handles PCM 16-bit mono/stereo."""
    # Find 'data' chunk
    idx = data.find(b"data")
    if idx == -1:
        raise ValueError("Invalid WAV: no data chunk")

    num_channels = struct.unpack_from("<H", data, 22)[0]
    bits_per_sample = struct.unpack_from("<H", data, 34)[0]
    data_size = struct.unpack_from("<I", data, idx + 4)[0]
    raw = data[idx + 8: idx + 8 + data_size]

    if bits_per_sample == 16:
        num_samples = len(raw) // 2
        samples = np.array(
            struct.unpack(f"<{num_samples}h", raw[: num_samples * 2]),
            dtype=np.float32,
        ) / 32768.0
    elif bits_per_sample == 8:
        samples = np.array(list(raw), dtype=np.float32) / 128.0 - 1.0
    else:
        raise ValueError(f"Unsupported WAV bit depth: {bits_per_sample}")

    # Convert stereo to mono by averaging channels
    if num_channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)

    return samples


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


# ---------------------------------------------------------------------------
# Voice Identifier
# ---------------------------------------------------------------------------

class VoiceIdentifier:
    """Lightweight speaker identification using MFCC fingerprints."""

    def __init__(
        self,
        data_path: Path | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._data_path = data_path or Path("data/voice_profiles.json")
        self.confidence_threshold = confidence_threshold
        self._profiles: dict[str, VoiceProfile] = {}
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if self._data_path.exists():
            try:
                raw = json.loads(self._data_path.read_text())
                for entry in raw:
                    profile = VoiceProfile(**entry)
                    self._profiles[profile.member_id] = profile
            except Exception as e:
                logger.warning(f"Failed to load voice profiles: {e}")

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(p) for p in self._profiles.values()]
        self._data_path.write_text(json.dumps(payload, indent=2))

    # -- feature extraction -------------------------------------------------

    def _extract_features(self, audio_data: bytes, sample_rate: int = 16000) -> list[float]:
        """Extract MFCC features from raw audio, returning an averaged fingerprint.

        Returns a list of NUM_MFCC floats representing the mean MFCC vector.
        """
        signal = _bytes_to_signal(audio_data, sample_rate)
        if len(signal) < FFT_SIZE:
            # Pad short signals
            signal = np.pad(signal, (0, FFT_SIZE - len(signal)))
        mfcc = _extract_mfcc(signal, sample_rate)
        # Average over all frames -> single fingerprint vector
        return mfcc.mean(axis=0).tolist()

    # -- enroll / identify --------------------------------------------------

    def enroll(self, member_id: str, audio_data: bytes, sample_rate: int = 16000) -> VoiceProfile:
        """Enroll a voice sample for a family member.

        Multiple samples (3+) are recommended for reliable identification.
        """
        features = self._extract_features(audio_data, sample_rate)

        if member_id not in self._profiles:
            self._profiles[member_id] = VoiceProfile(member_id=member_id)

        profile = self._profiles[member_id]
        profile.embeddings.append(features)
        profile.sample_count = len(profile.embeddings)
        self._save()

        logger.info(
            f"Enrolled voice sample for {member_id} "
            f"({profile.sample_count}/{MIN_SAMPLES_FOR_ID} samples)"
        )
        return profile

    def identify(
        self, audio_data: bytes, sample_rate: int = 16000
    ) -> tuple[str | None, float]:
        """Identify a speaker from audio.

        Returns (member_id, confidence). If no match exceeds the confidence
        threshold, returns (None, best_confidence).
        """
        if not self._profiles:
            return None, 0.0

        query = np.array(self._extract_features(audio_data, sample_rate))

        best_id: str | None = None
        best_score: float = -1.0

        for member_id, profile in self._profiles.items():
            if profile.sample_count < MIN_SAMPLES_FOR_ID:
                continue

            # Compare against average of all enrolled embeddings
            embeddings = np.array(profile.embeddings)
            centroid = embeddings.mean(axis=0)
            score = _cosine_similarity(query, centroid)

            if score > best_score:
                best_score = score
                best_id = member_id

        if best_score >= self.confidence_threshold:
            return best_id, best_score

        return None, best_score

    # -- profile management -------------------------------------------------

    def get_profile(self, member_id: str) -> VoiceProfile | None:
        return self._profiles.get(member_id)

    def list_profiles(self) -> list[VoiceProfile]:
        return list(self._profiles.values())

    def remove_profile(self, member_id: str) -> bool:
        if member_id in self._profiles:
            del self._profiles[member_id]
            self._save()
            return True
        return False

    def is_ready(self, member_id: str) -> bool:
        """Check whether a member has enough samples for identification."""
        profile = self._profiles.get(member_id)
        if not profile:
            return False
        return profile.sample_count >= MIN_SAMPLES_FOR_ID


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_voice_identifier: VoiceIdentifier | None = None


def get_voice_identifier() -> VoiceIdentifier:
    global _voice_identifier
    if _voice_identifier is None:
        _voice_identifier = VoiceIdentifier()
    return _voice_identifier
