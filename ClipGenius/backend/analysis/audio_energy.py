"""
ClipGenius - Audio Energy Analyzer
====================================
Analyses audio waveforms to detect high-energy moments that
often correspond to viral/engaging segments of a video.

Uses librosa to compute:
    - RMS energy envelope
    - Spectral centroid (brightness)
    - Zero-crossing rate (percussiveness / speech activity)
    - Onset strength (sudden changes)
"""

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import librosa
from loguru import logger

from backend.config import Config


@dataclass
class EnergyFrame:
    """Energy information for a single time window."""
    timestamp: float       # Centre time of this frame (seconds)
    rms_energy: float      # Root mean square energy (0-1 normalised)
    spectral_centroid: float  # Brightness / frequency centre (normalised)
    zcr: float             # Zero crossing rate (normalised)
    onset_strength: float  # Onset strength (normalised)
    combined_score: float  # Weighted combination of all signals


class AudioEnergyAnalyzer:
    """
    Analyses an audio file and produces a per-second energy profile.

    The profile is used by the Scorer to find the most engaging
    time windows for clip extraction.
    """

    # Weights for combining individual signals into a single score
    WEIGHT_RMS = 0.40          # Loudness is the strongest viral signal
    WEIGHT_ONSET = 0.30        # Sudden changes (reactions, drops)
    WEIGHT_SPECTRAL = 0.15     # High-frequency content (excitement)
    WEIGHT_ZCR = 0.15          # Speech / percussive activity

    def __init__(self):
        self._y: np.ndarray | None = None      # Audio time series
        self._sr: int = Config.AUDIO_SAMPLE_RATE
        self._duration: float = 0.0

    def analyze(self, audio_path: Path) -> list[EnergyFrame]:
        """
        Run full energy analysis on the given audio file.

        Args:
            audio_path: Path to the WAV audio file.

        Returns:
            List of EnergyFrame objects, one per second of audio.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting audio energy analysis: {audio_path}")

        # Load audio
        self._y, self._sr = librosa.load(
            str(audio_path),
            sr=Config.AUDIO_SAMPLE_RATE,
            mono=True,
        )
        self._duration = librosa.get_duration(y=self._y, sr=self._sr)
        logger.info(f"Audio loaded: {self._duration:.1f}s, sample_rate={self._sr}")

        # Compute individual features
        rms = self._compute_rms()
        spectral = self._compute_spectral_centroid()
        zcr = self._compute_zcr()
        onset = self._compute_onset_strength()

        # Build per-second energy frames
        frames = self._build_frames(rms, spectral, zcr, onset)

        logger.info(f"Energy analysis complete: {len(frames)} frames generated")
        return frames

    @property
    def duration(self) -> float:
        """Duration of the loaded audio in seconds."""
        return self._duration

    def _compute_rms(self) -> np.ndarray:
        """
        Compute RMS energy — measures overall loudness.
        
        Higher RMS = louder audio = more likely to be an exciting moment.
        """
        hop = Config.HOP_LENGTH
        rms = librosa.feature.rms(y=self._y, hop_length=hop)[0]
        rms_normalised = self._normalise(rms)
        logger.debug(f"RMS computed: {len(rms)} frames, max={rms_normalised.max():.3f}")
        return rms_normalised

    def _compute_spectral_centroid(self) -> np.ndarray:
        """
        Compute spectral centroid — measures the 'brightness' of audio.
        
        Higher centroid = brighter/more excited sound.
        Useful for detecting energetic speech, music peaks.
        """
        hop = Config.HOP_LENGTH
        centroid = librosa.feature.spectral_centroid(
            y=self._y, sr=self._sr, hop_length=hop
        )[0]
        centroid_normalised = self._normalise(centroid)
        logger.debug(f"Spectral centroid computed: {len(centroid)} frames")
        return centroid_normalised

    def _compute_zcr(self) -> np.ndarray:
        """
        Compute zero-crossing rate — measures percussiveness / noise.
        
        High ZCR correlates with speech activity and percussive sounds.
        Useful for detecting dialogue-heavy or action-packed segments.
        """
        hop = Config.HOP_LENGTH
        zcr = librosa.feature.zero_crossing_rate(y=self._y, hop_length=hop)[0]
        zcr_normalised = self._normalise(zcr)
        logger.debug(f"ZCR computed: {len(zcr)} frames")
        return zcr_normalised

    def _compute_onset_strength(self) -> np.ndarray:
        """
        Compute onset strength envelope — measures sudden audio changes.
        
        High onset strength = sudden change in audio energy.
        Great for detecting: reactions, claps, scene transitions, beat drops.
        """
        hop = Config.HOP_LENGTH
        onset = librosa.onset.onset_strength(y=self._y, sr=self._sr, hop_length=hop)
        onset_normalised = self._normalise(onset)
        logger.debug(f"Onset strength computed: {len(onset)} frames")
        return onset_normalised

    def _build_frames(
        self,
        rms: np.ndarray,
        spectral: np.ndarray,
        zcr: np.ndarray,
        onset: np.ndarray,
    ) -> list[EnergyFrame]:
        """
        Combine all feature arrays into per-second EnergyFrame objects.

        Each feature array has different lengths (based on hop length),
        so we resample them all to one-per-second resolution.
        """
        num_seconds = int(self._duration)
        if num_seconds == 0:
            return []

        # Resample each feature to one value per second
        rms_sec = self._resample_to_seconds(rms, num_seconds)
        spectral_sec = self._resample_to_seconds(spectral, num_seconds)
        zcr_sec = self._resample_to_seconds(zcr, num_seconds)
        onset_sec = self._resample_to_seconds(onset, num_seconds)

        frames = []
        for i in range(num_seconds):
            combined = (
                self.WEIGHT_RMS * rms_sec[i]
                + self.WEIGHT_ONSET * onset_sec[i]
                + self.WEIGHT_SPECTRAL * spectral_sec[i]
                + self.WEIGHT_ZCR * zcr_sec[i]
            )

            frame = EnergyFrame(
                timestamp=float(i) + 0.5,  # Centre of the second
                rms_energy=float(rms_sec[i]),
                spectral_centroid=float(spectral_sec[i]),
                zcr=float(zcr_sec[i]),
                onset_strength=float(onset_sec[i]),
                combined_score=float(combined),
            )
            frames.append(frame)

        return frames

    def _resample_to_seconds(self, arr: np.ndarray, num_seconds: int) -> np.ndarray:
        """
        Resample a feature array to exactly *num_seconds* values.
        
        Each output value is the mean of the corresponding 1-second window
        from the input array.
        """
        if len(arr) == 0:
            return np.zeros(num_seconds)

        # Number of feature frames per second of audio
        frames_per_sec = len(arr) / self._duration

        result = np.zeros(num_seconds)
        for sec in range(num_seconds):
            start_idx = int(sec * frames_per_sec)
            end_idx = int((sec + 1) * frames_per_sec)
            end_idx = min(end_idx, len(arr))
            if start_idx < end_idx:
                result[sec] = np.mean(arr[start_idx:end_idx])

        return result

    @staticmethod
    def _normalise(arr: np.ndarray) -> np.ndarray:
        """Min-max normalise an array to [0, 1] range."""
        arr_min = arr.min()
        arr_max = arr.max()
        if arr_max - arr_min < 1e-10:
            return np.zeros_like(arr)
        return (arr - arr_min) / (arr_max - arr_min)
