"""Simple voice emotion backend using basic audio features.

MVP approach: extract RMS energy, zero-crossing rate, and pitch variance
from audio to estimate arousal and intensity. No heavy ML models needed.

Accuracy: ~40-50% (rough estimate). Combined with text emotion (Claude),
the fusion result is much better.

Phase 2: Replace with SenseVoice-Small or GigaAM-Emo for 75-82% accuracy.
"""

import logging

import numpy as np

from skills.emotion.backends.base import VoiceEmotionBackend
from skills.emotion.pipeline import EmotionState, EMOTION_DEFAULTS

logger = logging.getLogger(__name__)


class SimpleVoiceBackend(VoiceEmotionBackend):
    """Rule-based voice emotion from audio features."""

    async def analyze(self, audio: np.ndarray, sample_rate: int = 16000) -> EmotionState:
        if len(audio) < sample_rate * 0.1:  # Less than 100ms
            return EmotionState(primary="neutral", confidence=0.1, source="voice")

        # ── Feature extraction ────────────────────────────────────
        rms = self._rms_energy(audio)
        zcr = self._zero_crossing_rate(audio)
        pitch_var = self._pitch_variance(audio, sample_rate)

        # ── Rule-based classification ─────────────────────────────
        # High energy + high ZCR → angry or excited
        # Low energy + low ZCR → sad or calm
        # High energy + low ZCR → happy/confident
        # High pitch variance → emotional expressiveness

        arousal = min(1.0, rms * 8)        # Normalize RMS to 0-1 range
        agitation = min(1.0, zcr * 5)      # ZCR as agitation indicator
        expressiveness = min(1.0, pitch_var * 2)

        # Determine primary emotion
        if arousal > 0.6 and agitation > 0.5:
            primary = "angry"
            valence = -0.5
        elif arousal > 0.5 and agitation < 0.4:
            primary = "happy"
            valence = 0.5
        elif arousal < 0.25:
            primary = "sad"
            valence = -0.4
        else:
            primary = "neutral"
            valence = 0.0

        # High expressiveness increases confidence in classification
        confidence = 0.2 + expressiveness * 0.3  # 0.2 - 0.5

        intensity = (arousal + expressiveness) / 2

        return EmotionState(
            primary=primary,
            intensity=min(1.0, intensity),
            valence=valence,
            arousal=arousal,
            intent="casual_chat",  # Voice alone can't determine intent well
            confidence=min(1.0, confidence),
            source="voice",
        )

    @staticmethod
    def _rms_energy(audio: np.ndarray) -> float:
        """Root mean square energy."""
        return float(np.sqrt(np.mean(audio ** 2)))

    @staticmethod
    def _zero_crossing_rate(audio: np.ndarray) -> float:
        """Zero-crossing rate — frequency of sign changes."""
        signs = np.sign(audio)
        crossings = np.sum(np.abs(np.diff(signs)) > 0)
        return float(crossings / len(audio))

    @staticmethod
    def _pitch_variance(audio: np.ndarray, sample_rate: int) -> float:
        """Estimate pitch variance using autocorrelation.

        Higher variance = more emotional expressiveness.
        """
        try:
            # Simple autocorrelation-based pitch estimation
            frame_size = min(2048, len(audio))
            n_frames = max(1, len(audio) // frame_size)
            pitches = []

            for i in range(n_frames):
                frame = audio[i * frame_size: (i + 1) * frame_size]
                if len(frame) < frame_size:
                    break

                # Autocorrelation
                corr = np.correlate(frame, frame, mode='full')
                corr = corr[len(corr) // 2:]

                # Find first peak after the initial decay
                min_lag = sample_rate // 500   # Max 500Hz
                max_lag = sample_rate // 50    # Min 50Hz

                if max_lag >= len(corr):
                    continue

                search = corr[min_lag:max_lag]
                if len(search) == 0:
                    continue

                peak = np.argmax(search) + min_lag
                if peak > 0 and corr[peak] > 0.2 * corr[0]:
                    pitch = sample_rate / peak
                    pitches.append(pitch)

            if len(pitches) < 2:
                return 0.0

            return float(np.std(pitches) / (np.mean(pitches) + 1e-6))

        except Exception:
            return 0.0
