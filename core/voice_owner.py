# -*- coding: utf-8 -*-
"""Owner-only voice verification. Accepts only the enrolled owner's voice."""

import os
import numpy as np
from scipy import signal
from scipy.fft import fft
import config.settings as settings


def _extract_features(audio: np.ndarray, sr: int) -> np.ndarray:
    """Extract a compact voice print: MFCC-like + energy + spectral stats."""
    if len(audio) < sr // 10:  # need at least 0.1s
        return np.zeros(32, dtype=np.float32)
    # Pre-emphasis
    audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])
    # Frame (e.g. 25ms)
    frame_len = int(sr * 0.025)
    hop = int(sr * 0.010)
    n_frames = max(1, (len(audio) - frame_len) // hop + 1)
    features = []
    for i in range(min(n_frames, 50)):  # cap frames
        start = i * hop
        frame = audio[start : start + frame_len]
        if len(frame) < frame_len:
            frame = np.pad(frame, (0, frame_len - len(frame)))
        # Window
        frame = frame * np.hamming(frame_len)
        # Magnitude spectrum
        mag = np.abs(fft(frame))[: frame_len // 2 + 1]
        # Log energy bands (coarse MFCC-like)
        n_bands = 8
        band_edges = np.linspace(0, len(mag) - 1, n_bands + 1, dtype=int)
        band_energies = []
        for b in range(n_bands):
            low, high = band_edges[b], band_edges[b + 1]
            band_energies.append(np.log1p(np.sum(mag[low:high] ** 2)))
        features.extend(band_energies)
    # Global stats over frames (mean of first 8 bands, std of next 8, etc.)
    arr = np.array(features, dtype=np.float32)
    if arr.size < 32:
        arr = np.pad(arr, (0, 32 - arr.size))
    # Single vector: mean + std of band energies over time
    n_bands = 8
    n_f = min(n_frames, 50)
    mat = arr[: n_bands * n_f].reshape(-1, n_bands)
    mean_b = mat.mean(axis=0)
    std_b = mat.std(axis=0)
    return np.concatenate([mean_b, std_b, np.array([np.log1p(np.mean(audio ** 2))] * 16)[:16]])[:32].astype(np.float32)


class OwnerVoiceVerifier:
    """Verifies that the current speaker is the enrolled owner."""

    def __init__(self):
        self.voice_print_path = settings.VOICE_PRINT_PATH
        self.threshold = settings.OWNER_VOICE_SIMILARITY_THRESHOLD
        self._mean: np.ndarray | None = None
        self._cov_inv: np.ndarray | None = None
        self._loaded = False
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.voice_print_path):
            self._loaded = False
            return
        try:
            data = np.load(self.voice_print_path)
            self._mean = data["mean"]
            self._cov_inv = data["cov_inv"]
            self._loaded = True
        except Exception:
            self._loaded = False

    def is_enrolled(self) -> bool:
        return self._loaded

    def enroll(self, audio_samples: list[np.ndarray], sr: int) -> bool:
        """Enroll owner from a list of audio buffers (e.g. 3x 'I am the owner')."""
        if len(audio_samples) < settings.VOICE_PRINT_SAMPLES_NEEDED:
            return False
        features = np.array([_extract_features(s, sr) for s in audio_samples], dtype=np.float32)
        mean = features.mean(axis=0)
        cov = np.cov(features.T)
        cov += np.eye(cov.shape[0]) * 1e-4
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            cov_inv = np.eye(len(mean))
        os.makedirs(os.path.dirname(self.voice_print_path), exist_ok=True)
        np.savez(self.voice_print_path, mean=mean, cov_inv=cov_inv)
        self._mean = mean
        self._cov_inv = cov_inv
        self._loaded = True
        return True

    def verify(self, audio: np.ndarray, sr: int) -> bool:
        """Return True only if the audio matches the owner's voice print."""
        if not self._loaded:
            return False
        feat = _extract_features(audio, sr)
        diff = feat - self._mean
        # Mahalanobis-like score (lower = more similar)
        d = np.dot(diff, np.dot(self._cov_inv, diff))
        # Convert to similarity in [0,1]; higher = more similar
        similarity = 1.0 / (1.0 + np.sqrt(d))
        return similarity >= self.threshold
