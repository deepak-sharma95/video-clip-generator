"""
ClipGenius - Viral Moment Scorer
==================================
Finds the best time windows for clip extraction using sliding window analysis.
"""

from dataclasses import dataclass, field
import numpy as np
from loguru import logger
from backend.config import Config
from backend.analysis.audio_energy import EnergyFrame


@dataclass
class ViralMoment:
    """A detected viral moment in the video."""
    rank: int
    start_time: float
    end_time: float
    duration: float
    viral_score: float
    peak_energy: float
    avg_energy: float
    reason: str = ""
    energy_profile: list[float] = field(default_factory=list)

    @property
    def start_timestamp(self) -> str:
        mins, secs = divmod(int(self.start_time), 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def end_timestamp(self) -> str:
        mins, secs = divmod(int(self.end_time), 60)
        return f"{mins:02d}:{secs:02d}"


class Scorer:
    """Finds the most viral moments based on audio energy analysis."""

    SPIKE_BONUS = 1.25
    SPIKE_THRESHOLD_STD = 1.5
    SMOOTH_WINDOW = 3

    def __init__(self, clip_duration=None, max_clips=None):
        self.clip_duration = clip_duration or Config.DEFAULT_CLIP_DURATION
        self.max_clips = max_clips or Config.MAX_CLIPS

    def find_viral_moments(self, frames, video_duration):
        if not frames or len(frames) < self.clip_duration:
            logger.warning("Not enough frames for analysis")
            return []

        logger.info(f"Scoring {len(frames)} frames — clip={self.clip_duration}s, max={self.max_clips}")
        raw_scores = np.array([f.combined_score for f in frames])
        smoothed = self._smooth(raw_scores, self.SMOOTH_WINDOW)
        spike_thresh = np.mean(raw_scores) + self.SPIKE_THRESHOLD_STD * np.std(raw_scores)

        window_scores = self._score_windows(smoothed, raw_scores, spike_thresh)
        moments = self._select_top(window_scores, frames, raw_scores)

        for m in moments:
            logger.info(f"  #{m.rank}: {m.start_timestamp}->{m.end_timestamp} score={m.viral_score:.3f}")
        return moments

    def _score_windows(self, smoothed, raw, spike_thresh):
        n, dur = len(smoothed), self.clip_duration
        num_w = n - dur + 1
        if num_w <= 0:
            return np.array([])
        scores = np.zeros(num_w)
        for i in range(num_w):
            avg = np.mean(smoothed[i:i+dur])
            if np.max(raw[i:i+dur]) > spike_thresh:
                avg *= self.SPIKE_BONUS
            # Penalise intro (first 10%) and outro (last 5%)
            rel = i / num_w
            if rel < 0.10:
                avg *= 0.80
            elif rel > 0.95:
                avg *= 0.75
            scores[i] = avg
        return scores

    def _select_top(self, window_scores, frames, raw_scores):
        if len(window_scores) == 0:
            return []
        sorted_idx = np.argsort(window_scores)[::-1]
        selected, used = [], []
        min_gap = Config.PEAK_MIN_DISTANCE_SEC

        for idx in sorted_idx:
            if len(selected) >= self.max_clips:
                break
            s, e = int(idx), int(idx) + self.clip_duration
            if any(not (e + min_gap <= us or s >= ue + min_gap) for us, ue in used):
                continue

            wr = raw_scores[s:e]
            wf = frames[s:e]
            moment = ViralMoment(
                rank=len(selected)+1, start_time=float(s), end_time=float(e),
                duration=float(self.clip_duration), viral_score=float(window_scores[idx]),
                peak_energy=float(np.max(wr)), avg_energy=float(np.mean(wr)),
                reason=self._reason(wf), energy_profile=[float(x) for x in wr],
            )
            selected.append(moment)
            used.append((s, e))

        if selected:
            mx = selected[0].viral_score
            if mx > 0:
                for m in selected:
                    m.viral_score /= mx
        return selected

    def _reason(self, wf):
        if not wf:
            return "High energy segment"
        reasons = []
        avg_rms = np.mean([f.rms_energy for f in wf])
        avg_onset = np.mean([f.onset_strength for f in wf])
        if avg_rms > 0.6:
            reasons.append("High audio energy (loud moment)")
        if avg_onset > 0.5:
            reasons.append("Sudden audio changes detected")
        energies = [f.combined_score for f in wf]
        if max(energies) > 2 * np.mean(energies):
            reasons.append("Contains sharp energy spike")
        return " + ".join(reasons) if reasons else "Above-average engagement signals"

    @staticmethod
    def _smooth(arr, window):
        if window <= 1 or len(arr) <= window:
            return arr.copy()
        return np.convolve(arr, np.ones(window)/window, mode="same")
