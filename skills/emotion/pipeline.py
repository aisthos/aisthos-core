"""Emotion Recognition Pipeline — orchestrates voice + text + visual backends.

Architecture:
  VoiceBackend (audio → emotion)  ─┐
  TextBackend  (text  → emotion)  ─┼─→ EmotionFusion → EmotionState
  VisualBackend (frame → emotion) ─┘    (weighted merge)

MVP: SimpleVoice + Claude text prompt (zero extra API calls).
Phase 2: SenseVoice, GigaAM-Emo, GigaChat, Aniemore.
Phase 3: Camera via VisualBackend.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Valid emotion labels
EMOTIONS = {"happy", "sad", "angry", "neutral", "surprised", "fear"}
INTENTS = {"needs_support", "wants_advice", "casual_chat", "excited_sharing", "focused_work"}

# Emotion → valence/arousal defaults (used when backend returns only primary)
EMOTION_DEFAULTS = {
    "happy":     {"valence":  0.7, "arousal": 0.6},
    "sad":       {"valence": -0.6, "arousal": 0.2},
    "angry":     {"valence": -0.7, "arousal": 0.8},
    "neutral":   {"valence":  0.0, "arousal": 0.3},
    "surprised": {"valence":  0.3, "arousal": 0.8},
    "fear":      {"valence": -0.5, "arousal": 0.7},
}


@dataclass
class EmotionState:
    """Unified emotion representation across all backends."""
    primary: str = "neutral"        # happy, sad, angry, neutral, surprised, fear
    intensity: float = 0.5          # 0.0 - 1.0
    valence: float = 0.0            # -1.0 (negative) to +1.0 (positive)
    arousal: float = 0.3            # 0.0 (calm) to 1.0 (excited)
    intent: str = "casual_chat"     # needs_support, wants_advice, casual_chat, etc.
    aspects: list = field(default_factory=list)  # [{"topic": "...", "emotion": "..."}]
    confidence: float = 0.5         # 0.0 - 1.0
    source: str = "unknown"         # "voice", "text", "fusion", "default"

    def to_dict(self) -> dict:
        """Serialize for WebSocket transmission."""
        return {
            "primary": self.primary,
            "intensity": round(self.intensity, 2),
            "valence": round(self.valence, 2),
            "arousal": round(self.arousal, 2),
            "intent": self.intent,
            "confidence": round(self.confidence, 2),
            "source": self.source,
        }

    @classmethod
    def default(cls) -> "EmotionState":
        """Return neutral default state."""
        return cls(primary="neutral", source="default")


# ── Emotion Tag Parser ────────────────────────────────────────────────

EMOTION_TAG_RE = re.compile(
    r"\[EMOTION:(\w+),([\d.]+),([-\d.]+),([\d.]+),(\w+)\]\s*"
)


def parse_emotion_tag(response: str) -> tuple[Optional[EmotionState], str]:
    """Parse [EMOTION:...] tag from Claude response.

    Returns:
        (emotion_state, clean_text) — emotion if found, cleaned response text.
    """
    match = EMOTION_TAG_RE.match(response)
    if not match:
        return None, response

    primary = match.group(1)
    if primary not in EMOTIONS:
        primary = "neutral"

    intent = match.group(5)
    if intent not in INTENTS:
        intent = "casual_chat"

    emotion = EmotionState(
        primary=primary,
        intensity=_clamp(float(match.group(2)), 0.0, 1.0),
        valence=_clamp(float(match.group(3)), -1.0, 1.0),
        arousal=_clamp(float(match.group(4)), 0.0, 1.0),
        intent=intent,
        confidence=0.75,  # Claude text-based = good confidence
        source="text",
    )

    clean_text = response[match.end():]
    return emotion, clean_text


# ── Emotion Fusion ────────────────────────────────────────────────────

def fuse_emotions(
    voice: Optional[EmotionState],
    text: Optional[EmotionState],
    voice_weight: float = 0.3,
    text_weight: float = 0.7,
) -> EmotionState:
    """Merge voice + text emotions into a single state.

    MVP: text-heavy weight because Claude text analysis is more reliable
    than simple audio features. Phase 2: rebalance when SenseVoice is added.
    """
    if voice is None and text is None:
        return EmotionState.default()
    if voice is None:
        return text
    if text is None:
        return voice

    # Text emotion wins for primary (more reliable for MVP)
    # Voice emotion modulates intensity and arousal
    total = voice_weight + text_weight
    vw = voice_weight / total
    tw = text_weight / total

    return EmotionState(
        primary=text.primary,  # trust text classification
        intensity=voice.intensity * vw + text.intensity * tw,
        valence=voice.valence * vw + text.valence * tw,
        arousal=voice.arousal * vw + text.arousal * tw,
        intent=text.intent,  # trust text for intent
        aspects=text.aspects,
        confidence=max(voice.confidence, text.confidence),
        source="fusion",
    )


# ── Helpers ───────────────────────────────────────────────────────────

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
