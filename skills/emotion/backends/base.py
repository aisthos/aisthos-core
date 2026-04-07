"""Abstract base classes for emotion recognition backends.

Each backend implements one modality (voice, text, or visual).
Backends are pluggable — swap via config without changing pipeline code.
"""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from skills.emotion.pipeline import EmotionState


class VoiceEmotionBackend(ABC):
    """Analyze emotion from audio signal."""

    @abstractmethod
    async def analyze(self, audio: np.ndarray, sample_rate: int = 16000) -> EmotionState:
        """Extract emotion from audio numpy array.

        Args:
            audio: Float32 audio data, normalized [-1.0, 1.0].
            sample_rate: Audio sample rate in Hz.

        Returns:
            EmotionState with source="voice".
        """
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class TextEmotionBackend(ABC):
    """Analyze emotion from text (transcription or direct input)."""

    @abstractmethod
    async def analyze(
        self,
        text: str,
        context: Optional[list[str]] = None,
    ) -> EmotionState:
        """Extract emotion from text with optional conversation context.

        Args:
            text: User's text input.
            context: Recent conversation messages for context.

        Returns:
            EmotionState with source="text".
        """
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class VisualEmotionBackend(ABC):
    """Analyze emotion from visual input (camera frame).

    Phase 3: camera not yet available.
    """

    @abstractmethod
    async def analyze(self, frame: Optional[np.ndarray] = None) -> EmotionState:
        """Extract emotion from camera frame.

        Args:
            frame: Image data (numpy array) or None if no camera.

        Returns:
            EmotionState with source="visual".
        """
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class NullVisualBackend(VisualEmotionBackend):
    """Placeholder for when no camera is available."""

    async def analyze(self, frame=None) -> EmotionState:
        return EmotionState(primary="neutral", confidence=0.0, source="visual")
